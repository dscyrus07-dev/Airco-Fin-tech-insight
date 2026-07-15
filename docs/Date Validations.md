The Problem

Your statement clearly shows:

01-09-2024
02-09-2024
03-09-2024
...
27-11-2024

which is:

DD-MM-YYYY

meaning:

01-09-2024 = 1 September 2024

But somewhere in your pipeline it is being interpreted as:

MM-DD-YYYY

so:

01-09-2024 = January 9, 2024

which causes:

Statement Start = Jan 2024
Statement End = Nov 2024

instead of:

Statement Start = Sep 2024
Statement End = Nov 2024
Never Use a Single Global Date Parser

Bad:

pd.to_datetime(date_string)

or

dateutil.parser.parse(date_string)

because they guess.

Example:

01-09-2024

can become:

1 Sep 2024
OR
9 Jan 2024

depending on locale.

Production Algorithm
Level 1 — Bank-Specific Date Format

Each bank should declare:

BANK_DATE_FORMAT = "%d-%m-%Y"

Example:

HDFC      -> %d/%m/%Y
SBI       -> %d-%m-%Y
BOB       -> %d-%m-%Y
ICICI     -> %d-%m-%Y
Kotak     -> %d-%m-%Y

Parser uses:

datetime.strptime(
    date_str,
    BANK_DATE_FORMAT
)

This should solve 90%.

Level 2 — Statement Header Validation

Your PDF itself contains:

Account Statement from 01-09-2024 to 27-11-2024

Extract this header.

Then:

header_start = 2024-09-01
header_end   = 2024-11-27

Use it as ground truth.

Level 3 — Transaction Sequence Validation

Transactions should be chronological.

Example:

01-09-2024
02-09-2024
03-09-2024
04-09-2024

If parser produces:

2024-01-09
2024-02-09
2024-03-09

that's impossible because months keep changing daily.

Flag:

DATE_FORMAT_SUSPECTED
Level 4 — Range Consistency Check

For this statement:

From: 01-09-2024
To:   27-11-2024

Expected duration:

≈ 87 days

If parsed dates become:

Jan 2024 → Nov 2024

Duration:

≈ 320 days

Impossible.

Automatically reject.

Level 5 — Month Frequency Analysis

Count months appearing.

Correct:

Sep 2024
Oct 2024
Nov 2024

3 months

Wrong interpretation:

Jan
Feb
Mar
Apr
May
Jun
Jul
Aug
Sep
Oct
Nov

11 months

while statement is only 63 pages.

Red flag.

Best Production Method

Create:

DateNormalizer
Step 1

Try bank format:

%d-%m-%Y
Step 2

Validate against header.

Step 3

Validate chronological order.

Step 4

Validate statement duration.

Step 5

Validate month distribution.

Step 6

Choose highest confidence interpretation.

Confidence-Based Approach

For:

01-09-2024

Generate:

Candidate A
2024-09-01

Score:

Header Match: +40
Chronology: +30
Range Match: +20
Month Distribution: +10

Total: 100
Candidate B
2024-01-09

Score:

Header Match: 0
Chronology: 5
Range Match: 0
Month Distribution: 0

Total: 5

Choose Candidate A.

Additional Audit Column

Store:

{
    "detected_date_format": "DD-MM-YYYY",
    "date_confidence": 0.99,
    "header_date_range":
    {
        "start": "2024-09-01",
        "end": "2024-11-27"
    }
}

inside metadata.

For Airco

The most reliable approach is:

Bank-specific format
+
Header date extraction
+
Chronological validation
+
Range validation

Don't rely on pd.to_datetime() guessing formats.