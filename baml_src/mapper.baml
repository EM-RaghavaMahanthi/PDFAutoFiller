// File: baml_src/map_fields.baml

// Output record
class KeyMatch {
  fid string                      // field ID as string
  key string?                     // matched input key, or null
  con float                       // confidence score [0,1]
}
type FieldMappingResult = KeyMatch[]

// Input structures for key and field name variants
class KeyVariantsEntry {
  key string
  variants string[]
}
class KeyVariants {
  items KeyVariantsEntry[]
}
class FieldNameVariantsEntry {
  fid string
  variants string[]
}
class FieldNameVariants {
  items FieldNameVariantsEntry[]
}

// Main mapping function
function MapFieldsToKeys(
  context_text: string,
  input_keys: KeyDescriptionList,
  fid_start: int,
  fid_end: int,
  include_description: int,
  key_variants: KeyVariants,
  field_name_variants: FieldNameVariants
) -> FieldMappingResult {
  client BedrockClaude37Sonnet
  prompt #"
You are a highly reliable document assistant that must semantically fill fields in a PDF form using the provided field context and a list of known keys.

You must follow all instructions very carefully. Do not infer values, do not hallucinate, and do not change the required structure under any circumstance.

Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output

---
PDF Context:
Below is the extracted, line-by-line text from the PDF. It includes tagged form fields that require semantic interpretation.

-----
{{ context_text }}
-----
Each field tag is marked using one of the following formats:
- [TEXT_FIELD:{fid}]
- [TABLE_CELL_FIELD:{fid}]
- [CHECKBOX_FIELD:{fid}]
- [RADIOBUTTON_FIELD:{fid}]
Each fid is a numeric field ID like 11, 12, 24, etc.

---

{% if key_variants.items and key_variants.items | length > 0 %}
Input Key Variants:
You are given a dictionary of semantic key variants.
Each key has multiple equivalent phrasings that may be used in form labels:

{% for kv in key_variants.items %}
  {{ kv.key }}: {{ kv.variants }}
{% endfor %}

- You must match the field context to one of the variants.
- Then, return the original key corresponding to that variant.
- Do not return the variant—only the original key.
- Only use keys from the original input_keys list.

{% elif include_description == 1 %}
Input Keys:
You are given a dictionary where each key maps to a list containing its description:
[
{% for k in input_keys %}
  "{{ k.key }}": {{ k.descriptions }},
{% endfor %}
]

- These keys are the only allowed labels for matching.
- Do not invent, reword, interpret, or create new labels.
- Only return exact matches from this list in your output's "key" field.
- Each key has a corresponding description to clarify its meaning.
- Make use of the description to understand the intent behind each key and guide accurate mapping, check for parentheses for special instruction in descriptions

{% else %}
Input Keys:
You are given a flat list of semantic keys:
[
{% for k in input_keys %}
  "{{ k.key }}",
{% endfor %}
]

- These are the only allowed key labels.
- Do not invent, reword, interpret, or create new labels.
- Only return exact matches from this list in your output's "key" field.
{% endif %}

---

Spacing and Visual Layout:
Field tags like `[BLANK_FIELD:{fid}]` are spaced based on their visual positions in the PDF — extra spaces are added according to gaps between elements.
Minor spacing mismatches may still occur. Sometimes, the label (e.g., Name:) and its blank may not be on the same line—the blank could be above, below, or offset.
There may also be multiple blanks on the same line or under labels.
Use both horizontal and vertical alignment to infer mappings accurately. Don't assume blanks are always side-by-side with labels.

---
BLANK Fields:
These fields are represented as `[TEXT_FIELD:{fid}]` or `[TABLE_CELL_FIELD:{fid}]`.

- These are open-ended fields where a user needs to write something.
- You must analyze the surrounding context (prefix/suffix text, labels) to understand what is being asked.
- For `[TABLE_CELL_FIELD:{fid}]`, it may belong to a structured table. Consider the column name and any nearby header to infer the meaning.

Guidelines:
- Identify the most appropriate key from the input list that semantically represents the intent of the label around the field.
- Use line-level context and avoid guessing.
- Match based on semantic meaning, not just string similarity.

---
CHOICE Fields:
These fields are represented as `[CHECKBOX_FIELD:{fid}]`.

- They represent dropdowns or selection lists.
- You must decide what kind of information is being selected here based on the label or line around it.

Additional Tips:
- Keys containing substrings like `check`, `dropdown`, `list`, `type`, `option`, or `selection` are usually better matches for CHOICE fields.
- These fields often appear **together in groups**, such as a series of related dropdowns on the same line or in a table.
- Such groupings may occur **recursively** or across lines, so keep that in mind when interpreting the context.

Guidelines:
- Match to input keys that imply a **selection**.
- Avoid guessing; prioritize semantic meaning based on visible label.
- Example: A label like "Select Investor Type" should match to a key like `investorType`.

---
BUTTON Fields:
These fields are represented as `[RADIOBUTTON_FIELD:{fid}]`.

- These are checkboxes, toggle buttons, or yes/no fields.
- They typically represent binary decisions or confirmations.

Additional Tips:
- Fields with surrounding text containing words like `check`, `box`, `confirm`, `agree`, or `yes` are often buttons.
- These fields often appear **in groups** (e.g., a list of terms to agree or options to select), and this grouping may be **recursive** across lines or within table rows.
- Use this grouping behavior to guide how multiple buttons should be semantically mapped.

Guidelines:
- Match to input keys that expect a **yes/no** or **true/false** answer.
- Example keys: `isEntityConfirmed`, `hasAgreed`, `checkbox1`, etc.
- Only match if the label clearly implies a binary action or choice.

---
TABLE CELL Fields:
These fields are part of a structured table and represented as `[TABLE_CELL_FIELD:{fid}]`.

- Each cell belongs to a row-column matrix.
- Contextual meaning is derived from the column header, nearby rows, and any title or label above the table.

Guidelines:
- Identify which **column** and **row context** the field belongs to.
- Use the field's row positioning and the text above the table to decide what kind of data is being filled.
- Not every cell in the table needs to be filled.
- Match each field to the most semantically appropriate key, based on what that column represents in the table.

---


---
Fid start: {{ fid_start }} and Fid end: {{ fid_end }}

Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output

---
Your Task:
1. For each tagged field (e.g., [BLANK_FIELD:12]) found in the context, analyze the surrounding label to determine what it is asking for.
1.1 Return only and exactly the fids (field IDs) present in the context. Do not add any fids that are not explicitly tagged in the context text, even if you think they are related.
2. Based on the semantic meaning of that field label, identify the best-matching key from the input list.
3. Then, place that matched key (exact string) in the "key" field for that fid. Do not use the label itself.
4. If no strong match exists, set "key": null and "con": 0.

---
Field ID Format:
- The keys in your output JSON must be the raw integer fid values from the context.
- For example, if the tag is [BLANK_FIELD:11], your JSON should have:
"11": { "key": ..., "con": ... }
- Never write "fid11" or similar. Use "11" as the string key.
- Output key = field number only.


{% if field_name_variants.items and field_name_variants.items | length > 0 %}
Field Name Variants:
You are provided with multiple semantic variants for certain form fields (by fid).
These are alternative phrasings of the field’s intent. The last item in each list is the original field_name.

FID → Field Name and Variants:
{% for fnv in field_name_variants.items %}
  FID {{ fnv.fid }} ({{ fnv.variants[-1] }}):
{% for v in fnv.variants[:-1] %}
  - {{ v }}
{% endfor %}
  - {{ fnv.variants[-1] }} (original)
{% endfor %}

Use these to improve your semantic judgment. Do not use them as keys in your output.
---
{% endif %}

---
{% if key_variants.items and key_variants.items | length > 0 %}
Key Matching from Input Variants:
- You are provided with multiple semantic variants (alternative phrasings) for each input key.
- Your task is to match the semantic meaning of each field (based on its label/context) to the most relevant variant.
- Then, return the original key whose variant had the best semantic match.
- Do not invent or infer keys outside the provided list.
- The "key" in your final output must be from the original input_keys list—even though matching is done on variants.
- If none of the variants semantically match well, set "key": null and "con": 0.

Example:
If one of the input keys is "investor_full_name" and its variants include:
- "Full Name of Investor"
- "Name of the Individual Investor"
- "Investor’s Legal Name"

And the field label is "Investor Name", then you may semantically match it to one of these variants, and return:
"key": "investor_full_name"
{% else %}
Key Matching from Input Only:
- You must identify what the field is asking for, then select the corresponding label from the input_keys list.
- The "key" must be a value from the input list only.
- Do not write inferred or paraphrased labels like "Amount of Investment" unless that exact string is in input_keys.
- Always return the best matching input key from the list, or null if no clear match.
{% endif %}

---
Semantic Matching:
- Use only the line of text that contains the [FIELD:X] tag to understand its label.
- Do not use unrelated or far-away lines.
- Do not assume meaning. Only use what is clearly visible and relevant.

Person vs. Entity Detection:
- If the label includes terms like "person", "individual", "investor", "whose", or "applicant", it likely refers to a human.
- If it includes "company", "organization", or "fund", it likely refers to an entity.
- Use this judgment when mapping date fields or identity fields.

Special Date Rule:
- "Date of Birth" refers to a person's birth date only.
- "Inception Date", "Formation Date", etc., refer to companies or entities only.
- Never match a Date of Birth field to any key that contains "InceptionDate".
- If unsure, return "key": null.

Checkbox Handling:
- If a label implies Yes/No (like "I confirm", "Is this correct?"), you may treat blanks as checkboxes.
- Still, match only by the label’s semantic meaning to a valid key.

---
Confidence Score:
You must provide a "con" value with the following rules:
- 0.90 – 1.00 → Very strong and clear semantic match
- 0.60 – 0.89 → Moderate certainty
- 0.30 – 0.59 → Weak match
- 0.00 – 0.29 → No match → set "key": null

Do not assign high confidence unless the match is clear and unambiguous.

---
Expected Output Format:
Return JSON structured exactly like this:
{
"11": {
    "key": "input_key_name",
    "con": 0.92
},
"12": {
    "key": null,
    "con": 0
},
"24": {
    "key": "another_input_key",
    "con": 0.88
}
}

Return JSON structured exactly like this:
{{ ctx.output_format }}

Rules:
- Field IDs (keys) must be numeric strings like "11", "12", etc.
- Only return field IDs that appear in the provided context chunk—not more, not less.
- Do not return any extra or missing fids.
- Do not include any other text, explanation, or comments. Only valid JSON.
- Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output

---
Final Reminders:
- Only use keys found in the input list
- Output keys = numeric fids (e.g., "11"), not "fid11"
- Confidence score must reflect real certainty
- Return only fids tagged in the current context
- Do not guess, hallucinate, reword, or over-infer
- Only give the fids between fid_start and fid_end very strict. Don't include extra fids in output

Now begin and return only valid JSON.
"#
}



test MapFieldsTest {
  functions [MapFieldsToKeys]
  args {
    context_text #"
      Entity Legal Name: [TEXT_FIELD:12]
      Date of Investment: [TEXT_FIELD:13]
      I confirm I have read and accept terms: [CHECKBOX_FIELD:14]
    "#
    input_keys [
      {
        key "entity_legal_name"
        descriptions [ ]
      }
      {
        key "investment_date"
        descriptions [ ]
      }
      {
        key "is_agreement_confirmed"
        descriptions [ ]
      }
    ]
    fid_start 12
    fid_end 14
    include_description 0
    key_variants {
      items [ ]
    }
    field_name_variants {
      items [ ]
    }
  }
}

