"""Station owners: phone + OTP sign-in, one bill, one station, then the station home.

The only station data source in the initial stage is what owners upload - an
electricity bill (a photo or PDF, or units typed in by hand). Nothing here reads
a scraped inventory.

``/owner/signup`` and ``/owner/login`` - a mobile number and a password. There is
no email and no account form. There is no password reset yet; a one-time-code
method (``domain/owner/otp.py``) comes later. The number is not verified by a
code, so it is only a login name.

``/owner/bill-images`` - keep the uploaded bill so the owner can check figures
against it (deleted after the retention period, or on request), and return
whatever an extractor proposes. The first extractor proposes nothing:
the owner types the fields beside the image.

``/owner/onboard`` and ``/owner/stations/{id}/bills`` - store a station and/or a
bill *only when the owner has confirmed the fields* (``confirmed: true``).

``/owner/stations`` and ``/owner/stations/{id}/home`` - portfolio table and the
station page, read from confirmed bills and the forecasts stored when they were
made. The maths lives in ``app.domain.owner``; the browser computes nothing.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import uuid
from typing import Literal

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.internal.owner_privacy import NoStoreRoute
from app.api.internal.ratelimit import (
    check_phone_attempts,
    owner_auth_limit,
    owner_submit_limit,
)
from app.config import Settings, get_settings
from app.db import get_session
from app.domain.owner import password as owner_password
from app.domain.owner import session as owner_session
from app.domain.owner.area import OwnerAreaOut, area_context
from app.domain.owner.bill import BillExtractor, BillFields, ManualExtractor, resolve_meter
from app.domain.owner.erasure import delete_image, erase_account
from app.domain.owner.grid import (
    GridDetailsIn,
    OutageIn,
    OwnerGridOut,
    read_grid,
    save_grid,
    save_outage,
    withdraw_grid,
)
from app.domain.owner.home import PortfolioRow, StationHome, portfolio, station_home
from app.domain.owner.otp import mask_phone, normalise_phone
from app.domain.owner.service import (
    BillInvalidError,
    ConnectorSpec,
    StationSpec,
    add_bill,
    create_account,
    find_account,
    owned_station,
    register_station,
    station_count,
    store_image,
)
from app.domain.resolution import geography
from app.models.owner import OwnerAccount, OwnerBillImage

router = APIRouter(prefix="/owner")

_DEV_SECRET = "dev-only-owner-session-secret"  # noqa: S105 - refused in prod, see _secret
_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
Standard = Literal["CCS2", "CCS1", "CHAdeMO", "Type 2 AC", "GB/T", "Other"]


# --- dependencies -------------------------------------------------------------


def bill_extractor() -> BillExtractor:
    return ManualExtractor()


def _secret(settings: Settings) -> str:
    secret = settings.owner_session_secret or settings.console_secret_key
    if secret:
        return secret
    if settings.env == "prod":
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Owner sign-in is not configured.")
    return _DEV_SECRET


def current_owner(
    evsite_owner: str | None = Cookie(default=None, alias=owner_session.COOKIE_NAME),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> OwnerAccount:
    account_id = (
        owner_session.read(
            _secret(settings), evsite_owner, max_age_seconds=settings.owner_session_max_age_seconds
        )
        if evsite_owner
        else None
    )
    account = session.get(OwnerAccount, account_id) if account_id else None
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in with your phone number.")
    return account


# --- sign in --------------------------------------------------------------------


class CredentialsIn(BaseModel):
    phone: str = Field(max_length=24)
    password: str = Field(max_length=256)


class MeOut(BaseModel):
    #: The number with all but the last four digits hidden. The full number is never sent.
    phone_masked: str
    station_count: int


def _phone(raw: str) -> str:
    phone = normalise_phone(raw)
    if phone is None:
        raise HTTPException(422, "Enter a 10-digit Indian mobile number.")
    return phone


def _start_session(response: Response, settings: Settings, account_id: int) -> None:
    response.set_cookie(
        owner_session.COOKIE_NAME,
        owner_session.issue(_secret(settings), account_id),
        max_age=settings.owner_session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.env == "prod",
        path="/",
    )


@router.post(
    "/signup", response_model=MeOut, status_code=201, dependencies=[Depends(owner_auth_limit)]
)
def signup(
    body: CredentialsIn,
    response: Response,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> MeOut:
    phone = _phone(body.phone)
    if (why := owner_password.problem(body.password)) is not None:
        raise HTTPException(422, why)
    if find_account(session, phone) is not None:
        raise HTTPException(409, "This number already has an account. Log in instead.")
    account = create_account(
        session, phone, owner_password.make_hash(body.password), dt.datetime.now(dt.UTC)
    )
    _start_session(response, settings, account.id)
    return MeOut(phone_masked=mask_phone(phone), station_count=0)


@router.post("/login", response_model=MeOut, dependencies=[Depends(owner_auth_limit)])
def login(
    body: CredentialsIn,
    response: Response,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> MeOut:
    phone = _phone(body.phone)
    check_phone_attempts(phone, settings)
    account = find_account(session, phone)
    if not owner_password.check(body.password, account.password_hash if account else None):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Mobile number or password is not right.")
    assert account is not None  # noqa: S101 - check() never passes without an account
    account.last_login_at = dt.datetime.now(dt.UTC)
    _start_session(response, settings, account.id)
    return MeOut(phone_masked=mask_phone(phone), station_count=station_count(session, account.id))


@router.get("/me", response_model=MeOut)
def me(
    account: OwnerAccount = Depends(current_owner), session: Session = Depends(get_session)
) -> MeOut:
    return MeOut(
        phone_masked=mask_phone(account.phone), station_count=station_count(session, account.id)
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def erase_me(
    response: Response,
    account: OwnerAccount = Depends(current_owner),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> Response:
    """Erase the account and everything it holds: phone number, stations, bills, images."""
    erase_account(session, account.id)
    return logout(response, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, settings: Settings = Depends(get_settings)) -> Response:
    response.delete_cookie(
        owner_session.COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.env == "prod",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


# --- the bill image -------------------------------------------------------------

_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"%PDF-", "application/pdf"),
)


def _sniff(content: bytes) -> str | None:
    for magic, kind in _MAGIC:
        if content.startswith(magic):
            return kind
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


class ImageOut(BaseModel):
    image_id: uuid.UUID
    content_type: str
    size_bytes: int
    #: What an extractor proposes, if any. Nothing here is saved until the owner confirms.
    suggested: dict[str, str | float | int | None]
    extractor: str


@router.post("/bill-images", response_model=ImageOut, status_code=201)
def upload_bill_image(
    file: UploadFile,
    account: OwnerAccount = Depends(current_owner),
    settings: Settings = Depends(get_settings),
    extractor: BillExtractor = Depends(bill_extractor),
    session: Session = Depends(get_session),
) -> ImageOut:
    content = file.file.read(settings.owner_bill_max_bytes + 1)
    if len(content) > settings.owner_bill_max_bytes:
        raise HTTPException(413, "That file is too large. Send a photo or PDF under 8 MB.")
    kind = _sniff(content)
    if kind is None:
        raise HTTPException(415, "Send a photo (JPEG, PNG, WebP) or a PDF of the bill.")
    image = store_image(session, account.id, content, kind, hashlib.sha256(content).hexdigest())
    proposed = extractor.extract(content, kind)
    return ImageOut(
        image_id=image.id,
        content_type=kind,
        size_bytes=len(content),
        suggested={k: v for k, v in proposed.fields.items() if isinstance(v, str | float | int)},
        extractor=proposed.extractor,
    )


@router.get("/bill-images/{image_id}")
def bill_image(
    image_id: uuid.UUID,
    account: OwnerAccount = Depends(current_owner),
    session: Session = Depends(get_session),
) -> Response:
    image = session.get(OwnerBillImage, image_id)
    if image is None or image.account_id != account.id:
        raise HTTPException(404, "No such bill image.")
    return Response(
        image.data,
        media_type=image.content_type,
        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/bill-images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_bill_image(
    image_id: uuid.UUID,
    account: OwnerAccount = Depends(current_owner),
    session: Session = Depends(get_session),
) -> None:
    """Delete one bill image. The figures the owner confirmed from it stay."""
    if not delete_image(session, account.id, image_id):
        raise HTTPException(404, "No such bill image.")


# --- bills and stations ---------------------------------------------------------


def _month(value: str) -> dt.date:
    if not _MONTH.match(value):
        raise ValueError("month must be YYYY-MM")
    return dt.date(int(value[:4]), int(value[5:7]), 1)


class HistoryIn(BaseModel):
    period: str
    kwh: float = Field(allow_inf_nan=False)

    @field_validator("period")
    @classmethod
    def _check(cls, v: str) -> str:
        _month(v)
        return v


class BillIn(BaseModel):
    #: The owner has looked at each field and confirmed it. Required: extracted
    #: values are never saved on their own.
    confirmed: bool
    period: str
    kwh: float = Field(allow_inf_nan=False)
    image_id: uuid.UUID | None = None
    history: list[HistoryIn] = Field(default_factory=list, max_length=24)
    tariff_category: str | None = Field(default=None, max_length=80)
    contract_demand: float | None = Field(default=None, allow_inf_nan=False)
    recorded_demand: float | None = Field(default=None, allow_inf_nan=False)
    demand_unit: Literal["kVA", "kW"] | None = None
    power_factor: float | None = Field(default=None, allow_inf_nan=False)
    pf_effect: Literal["penalty", "incentive"] | None = None
    pf_amount_paise: int | None = Field(default=None, ge=0, le=10**11)
    tod_peak_kwh: float | None = Field(default=None, allow_inf_nan=False)
    tod_normal_kwh: float | None = Field(default=None, allow_inf_nan=False)
    tod_offpeak_kwh: float | None = Field(default=None, allow_inf_nan=False)
    board: str | None = Field(default=None, max_length=64)
    #: Only the last four characters are kept.
    consumer_number: str | None = Field(default=None, max_length=32)

    @field_validator("period")
    @classmethod
    def _check_period(cls, v: str) -> str:
        _month(v)
        return v


def _fields(bill: BillIn) -> BillFields:
    if not bill.confirmed:
        raise HTTPException(422, "Confirm each field before saving.")
    return BillFields(
        period=_month(bill.period),
        kwh=bill.kwh,
        history=tuple((_month(h.period), h.kwh) for h in bill.history),
        tariff_category=bill.tariff_category,
        contract_demand=bill.contract_demand,
        recorded_demand=bill.recorded_demand,
        demand_unit=bill.demand_unit,
        power_factor=bill.power_factor,
        pf_effect=bill.pf_effect,
        pf_amount_paise=bill.pf_amount_paise,
        tod_peak_kwh=bill.tod_peak_kwh,
        tod_normal_kwh=bill.tod_normal_kwh,
        tod_offpeak_kwh=bill.tod_offpeak_kwh,
        board=bill.board,
        consumer_number=bill.consumer_number,
    )


def _own_image(session: Session, account: OwnerAccount, image_id: uuid.UUID | None) -> None:
    if image_id is None:
        return
    image = session.get(OwnerBillImage, image_id)
    if image is None or image.account_id != account.id:
        raise HTTPException(422, "That bill image was not found. Upload it again.")


def _place(session: Session, lat: float, lng: float) -> tuple[str | None, str | None]:
    """State and district for a pin, or (None, None) outside coverage."""
    try:
        with session.begin_nested():
            hit = geography.resolve(session, lat, lng).district
    except Exception:  # noqa: BLE001 - a pin we cannot place is stored unplaced, not refused
        return None, None
    return (hit.state_name, hit.name) if hit else (None, None)


class ConnectorIn(BaseModel):
    standard: Standard
    power_kw: float = Field(gt=0, le=1000, allow_inf_nan=False)


class StationIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=300)
    lat: float = Field(ge=6.0, le=38.0)
    lng: float = Field(ge=68.0, le=98.0)
    #: The month it went live, YYYY-MM.
    went_live: str

    @field_validator("went_live")
    @classmethod
    def _check(cls, v: str) -> str:
        _month(v)
        return v


class OnboardIn(BaseModel):
    station: StationIn
    connectors: list[ConnectorIn] = Field(min_length=1, max_length=64)
    bill: BillIn
    #: "Does the charger have its own meter?" Asked only when the tariff
    #: category does not already settle it.
    meter_answer: Literal["separate", "shared", "unsure"] | None = None
    #: "Use my figures to benchmark and forecast my station. Only published as
    #: anonymised district averages of 10 or more stations." Required.
    consent_aggregate: bool


class SavedOut(BaseModel):
    station_id: int
    period: dt.date


def _invalid(exc: BillInvalidError) -> HTTPException:
    return HTTPException(422, " ".join(exc.errors))


@router.post(
    "/onboard",
    response_model=SavedOut,
    status_code=201,
    dependencies=[Depends(owner_submit_limit)],
)
def onboard(
    body: OnboardIn,
    account: OwnerAccount = Depends(current_owner),
    session: Session = Depends(get_session),
) -> SavedOut:
    fields = _fields(body.bill)
    _own_image(session, account, body.bill.image_id)
    state, district = _place(session, body.station.lat, body.station.lng)
    spec = StationSpec(
        name=body.station.name.strip(),
        address=body.station.address,
        lat=body.station.lat,
        lng=body.station.lng,
        state_name=state,
        district_name=district,
        went_live=_month(body.station.went_live),
        meter_type=resolve_meter(fields.tariff_category, body.meter_answer),
    )
    now = dt.datetime.now(dt.UTC)
    try:
        connectors = [ConnectorSpec(c.standard, c.power_kw) for c in body.connectors]
        station = register_station(
            session, account, spec, connectors, consent_aggregate=body.consent_aggregate, now=now
        )
        add_bill(session, station, fields, image_id=body.bill.image_id, today=now.date())
    except BillInvalidError as exc:
        raise _invalid(exc) from exc
    return SavedOut(station_id=station.id, period=fields.period)


class BillSaveIn(BaseModel):
    bill: BillIn


@router.post(
    "/stations/{station_id}/bills",
    response_model=SavedOut,
    status_code=201,
    dependencies=[Depends(owner_submit_limit)],
)
def save_bill(
    station_id: int,
    body: BillSaveIn,
    account: OwnerAccount = Depends(current_owner),
    session: Session = Depends(get_session),
) -> SavedOut:
    station = owned_station(session, account.id, station_id)
    if station is None:
        raise HTTPException(404, "No such station.")
    fields = _fields(body.bill)
    _own_image(session, account, body.bill.image_id)
    try:
        add_bill(
            session,
            station,
            fields,
            image_id=body.bill.image_id,
            today=dt.datetime.now(dt.UTC).date(),
        )
    except BillInvalidError as exc:
        raise _invalid(exc) from exc
    return SavedOut(station_id=station.id, period=fields.period)


@router.get("/stations", response_model=list[PortfolioRow])
def my_stations(
    account: OwnerAccount = Depends(current_owner), session: Session = Depends(get_session)
) -> list[PortfolioRow]:
    return portfolio(session, account.id)


@router.get("/stations/{station_id}/home", response_model=StationHome)
def home(
    station_id: int,
    account: OwnerAccount = Depends(current_owner),
    session: Session = Depends(get_session),
) -> StationHome:
    station = owned_station(session, account.id, station_id)
    if station is None:
        raise HTTPException(404, "No such station.")
    return station_home(session, station)


# --- Private grid display and public area context (Part 14) ------------------
private_grid_router = APIRouter(route_class=NoStoreRoute)
@private_grid_router.get("/stations/{station_id}/area", response_model=OwnerAreaOut)
def owner_area(
    station_id: int,
    response: Response,
    account: OwnerAccount = Depends(current_owner),
    session: Session = Depends(get_session),
) -> OwnerAreaOut:
    response.headers["Cache-Control"] = "no-store"
    return area_context(session, account.id, station_id)


@private_grid_router.get("/stations/{station_id}/grid", response_model=OwnerGridOut)
def owner_grid(
    station_id: int,
    response: Response,
    account: OwnerAccount = Depends(current_owner),
    session: Session = Depends(get_session),
) -> OwnerGridOut:
    response.headers["Cache-Control"] = "no-store"
    return read_grid(session, account.id, station_id)


@private_grid_router.post(
    "/stations/{station_id}/grid",
    response_model=OwnerGridOut,
    dependencies=[Depends(owner_submit_limit)],
)
def owner_grid_save(
    station_id: int,
    body: GridDetailsIn,
    response: Response,
    account: OwnerAccount = Depends(current_owner),
    session: Session = Depends(get_session),
) -> OwnerGridOut:
    response.headers["Cache-Control"] = "no-store"
    return save_grid(session, account.id, station_id, body)


@private_grid_router.post(
    "/stations/{station_id}/outages",
    response_model=OwnerGridOut,
    dependencies=[Depends(owner_submit_limit)],
)
def owner_outage_save(
    station_id: int,
    body: OutageIn,
    response: Response,
    account: OwnerAccount = Depends(current_owner),
    session: Session = Depends(get_session),
) -> OwnerGridOut:
    response.headers["Cache-Control"] = "no-store"
    return save_outage(session, account.id, station_id, body)


@private_grid_router.delete("/stations/{station_id}/grid", status_code=204)
def owner_grid_withdraw(
    station_id: int,
    response: Response,
    account: OwnerAccount = Depends(current_owner),
    session: Session = Depends(get_session),
) -> Response:
    withdraw_grid(session, account.id, station_id)
    response.headers["Cache-Control"] = "no-store"
    response.status_code = 204
    return response


router.include_router(private_grid_router)
