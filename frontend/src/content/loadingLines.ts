/**
 * Lines that rotate on the working screen while the assessment runs - the
 * product's answer to a food app's splash-screen jokes.
 *
 * Rules for adding a line, because this product's value is that every number
 * on a screen is traceable:
 *  - NO NUMBERS that read as facts. "EVs in your district grew 40%" is an
 *    unsourced figure wearing a joke. Durations of this very wait are fine.
 *  - Hand-written and reviewed. Never generated at runtime (AGENTS.md rule 11).
 *  - No utility or discom names: a state is rarely served by one, and a wrong
 *    one is a factual error, not a joke.
 *  - Regional lines need a native speaker's sign-off before they ship.
 */

export type DayPart = "night" | "morning" | "afternoon" | "evening";

export interface LoadingLine {
  text: string;
  /** Only shown in this part of the day, IST. */
  when?: DayPart;
  /** Only shown when the site is in this state - LGD name, upper case. */
  states?: readonly string[];
}

export const LOADING_LINES: readonly LoadingLine[] = [
  // Charging puns
  { text: "Charging up your answer. No range anxiety here." },
  { text: "Plugging into the tariff books…" },
  { text: "Counting chargers so you don't have to drive around doing it." },
  { text: "Even fast chargers take a minute. This takes less." },
  { text: "Reading the fine print on the electricity bill, so you don't have to." },

  // For the people who own the land
  { text: "For everyone who has looked at an empty plot and thought, “what if”." },
  { text: "Built for people who read their electricity bill twice." },
  { text: "Good sites aren't guessed. Give us a moment." },
  { text: "Your land, our homework." },

  // Time of day, IST
  { text: "Planning a charging business after midnight? Respect.", when: "night" },
  { text: "Chai first, then sanctioned load.", when: "morning" },
  { text: "Checking chargers on your lunch break? Same.", when: "afternoon" },
  { text: "Evening peak is when chargers earn their keep. Fitting time to ask.", when: "evening" },

  // Regional - native-speaker review pending for each
  { text: "Oru nimisham, ketto. Your site is being read.", states: ["KERALA"] },
  { text: "Konjam wait pannunga. Your site is being read.", states: ["TAMIL NADU", "PUDUCHERRY"] },
  { text: "Swalpa adjust maadi. Checking your site.", states: ["KARNATAKA"] },
  { text: "Konchem wait cheyyandi. Checking your site.", states: ["ANDHRA PRADESH", "TELANGANA"] },
  { text: "Thoda thamba. Your site is being read.", states: ["MAHARASHTRA", "GOA"] },
  { text: "Ektu darao. Your site is being read.", states: ["WEST BENGAL", "TRIPURA"] },
  { text: "Thodi vaar. Your site is being read.", states: ["GUJARAT"] },
  {
    text: "Bas do minute… actually, fifteen seconds.",
    states: [
      "UTTAR PRADESH",
      "BIHAR",
      "DELHI",
      "HARYANA",
      "RAJASTHAN",
      "MADHYA PRADESH",
      "CHHATTISGARH",
      "JHARKHAND",
      "UTTARAKHAND",
      "HIMACHAL PRADESH",
    ],
  },
];
