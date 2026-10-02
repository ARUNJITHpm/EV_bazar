import { Callout, Note, Section } from "./parts";

export function Disclosure() {
  return (
    <Section
      num="12"
      title="Disclosure and independence"
      heading="What we earn, and from whom."
      id="disclosure"
    >
      <p className="m-0 max-w-[74ch] text-[15px] leading-[1.65]">
        Chargeworthy provides site assessments and operator-matching services. Assessment and
        operator-matching fees are our income sources. We are not affiliated with any charge point
        operator. We do not own or operate charging stations and do not plan to own them.
      </p>
      <p className="mt-3 mb-0 max-w-[74ch] text-[15px] leading-[1.65]">
        Operator-matching fees create a potential commercial conflict. A comparison in this report
        does not establish a partnership, referral agreement, or endorsement. Demonstration terms
        and figures are illustrative; they are not a current offer from an operator.
      </p>
      <Note className="mt-3">
        No verified assessment counts or rejection rate are published here. Forecast accuracy
        against built sites is not yet established.
      </Note>
      <div className="mt-6">
        <Callout label="Disclose before this is used with a real client" tone="caution">
          <p>
            Record the assessment fee actually charged and who pays it. Disclose every referral or
            success fee attached to the site, its amount, who pays it, and any relationship with an
            operator named in section 06. Identify who commissioned the report.
          </p>
          <p>
            No actual fees or operator agreements are represented by this demonstration document.
          </p>
        </Callout>
      </div>
    </Section>
  );
}
