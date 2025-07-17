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

Only provide mappings for the fids (field IDs) between {{ fid_start }} and {{ fid_end }} **that actually appear in the provided context below**. Never add extra fids.

---

PDF Context:
Below is the extracted, line-by-line text from the PDF. It contains form fields marked by tags.

-----
{{ context_text }}
-----

Each field tag in the context appears as one of:
- [TEXT_FIELD:{fid}]
- [TABLE_CELL_FIELD:{fid}]
- [CHECKBOX_FIELD:{fid}]
- [RADIOBUTTON_FIELD:{fid}]
Each fid is a numeric string, e.g. "11".

---

{% if key_variants.items and key_variants.items | length > 0 %}
Input Keys—Semantic Variants Provided:
You are given a collection of keys, each with multiple variant phrasings. Use the variants to match meaning, but output **only the original key**.

{% for kv in key_variants.items %}
Key: {{ kv.key }}
Variants:
{% for v in kv.variants %}
- {{ v }}
{% endfor %}
{% endfor %}

- You must match the field context (label) to one of the provided variants, then use the original key for your answer.
- Do not invent, paraphrase, or create new labels.
- Return only keys present in the `input_keys` list.

{% elif include_description == 1 %}
Input Keys with Descriptions:
You are given a list of input keys (labels) and, separately, a description for each key.

- Each key is the only allowed label for matching.
- Only return **exact** matches from this list in your output's "key" field.
- Do not invent, reword, or interpret new labels.
- Each key’s associated description (provided earlier) clarifies its intended meaning and semantics.
- Carefully analyze the description for intent and special instructions (including those within parentheses).

List of keys:
{% for k in input_keys %}
- {{ k }}
{% endfor %}

{% else %}
Input Keys—Flat List:
You are given a list of allowed semantic keys.

- These are the only allowed key labels.
- Do not invent, reword, interpret, or create new labels.
- Only return exact matches from this list in your output's "key" field.

List of keys:
{% for k in input_keys %}
- {{ k }}
{% endfor %}
{% endif %}

---

Spacing and Visual Layout:
Field tags like `[BLANK_FIELD:{fid}]` are positioned based on their on-page layout. That means:
- A blank may not always appear on the same line as its label; it could be above, below, or offset.
- Multiple blanks may appear together or close to one label.
- Use both horizontal and vertical proximity and indentation to infer the correct mappings.
- Do not rely solely on line adjacency.

---

Field Types and Associated Guidelines:

BLANK Fields (e.g. `[TEXT_FIELD:{fid}]`, `[TABLE_CELL_FIELD:{fid}]`):
- These are open-ended fields. Use prefix/suffix text or nearby labels for meaning.
- For table cells, consider the column/row context and above-table headers.
- Match by semantic meaning—not just string similarity.

CHOICE Fields (`[CHECKBOX_FIELD:{fid}]`):
- Represents checkboxes, dropdowns, or selection lists.
- Match to input keys that imply a selection or option.
- Keys might include "check", "dropdown", "option", etc.
- These often appear in groups, sometimes recursively, across lines.

BUTTON Fields (`[RADIOBUTTON_FIELD:{fid}]`):
- Represent checkboxes or yes/no/binary toggles or confirmations.
- Usually imply true/false or agree/disagree logic.
- Search for words like "confirm", "agree", "yes" in nearby context.
- Grouped buttons may indicate a list of terms or options.

TABLE CELL Fields:
- Part of structured tables. Context comes from column name, headers, and row.
- Not every cell must be matched.
- Match to the most appropriate key for the role of that column/cell.

---

{% if field_name_variants.items and field_name_variants.items | length > 0 %}
Field Name Variants by Fid:

You are provided with lists of variant phrasings for specific fids.
The last item in each list is the original field name for that fid.

{% for fnv in field_name_variants.items %}
FID {{ fnv.fid }} ({{ fnv.variants[-1] }}):
{% for v in fnv.variants[:-1] %}
- {{ v }}
{% endfor %}
- {{ fnv.variants[-1] }} (original)
{% endfor %}

These variants are meant to help you understand complex or ambiguous field intent, but **do not use any of these as output keys**.
{% endif %}

---

Key Matching Rules:
{% if key_variants.items and key_variants.items | length > 0 %}
- Use the field context and semantic variants to identify the best match.
- Output the **original key** for the selected variant.
- If no adequate match, set "key": null and "con": 0.
- Do not invent new keys, nor output unlisted variants.
Example:
If the variants for "investor_full_name" include:
- "Full Name of Investor"
- "Legal Name of Investor"
and a label appears as "Investor Name", you may match the semantics to a variant, and output:
{ "fid": "...", "key": "investor_full_name", "con": ... }
{% else %}
- Only use exact keys from the flat input list.
- If unable to match, set "key": null and "con": 0.
{% endif %}

---

Semantic Guidance:
- Use only the same line as the field tag to glean context.
- Do not make assumptions from unrelated or distant lines.
- If the label refers to "person", "individual", etc., it denotes a human.
- If it says "company", "organization", or "fund", it's an entity.
- Never confuse "Date of Birth" with "Inception Date"/"Formation Date". Birth dates are for people, inception dates are for entities.
- When in doubt, set "key": null.

---

Formatting & Confidence Scores:
- Must output an array of mapping objects. Each object: { "fid", "key", "con" }
- Only output fids that are present in the context and within {{ fid_start }} to {{ fid_end }}—no more, no less.
- Confidence scoring:
    - 0.90–1.00: Very strong and clear match
    - 0.60–0.89: Moderate certainty
    - 0.30–0.59: Weak match
    - 0.29 or less: No match → "key": null
- Do not assign a high confidence unless the match is highly unambiguous.

---

Final Reminders:
- Do not guess, hallucinate, over-infer, or change required structure.
- If instructions seem ambiguous, stick as close as possible to context and list-approved keys.
- Every output object: include keys ("fid", "key", "con"). Key must always correspond to the input key list.
- Return **only** the strict output structure—no extra text, comments, or explanations.

{{ ctx.output_format }}
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
      "entity_legal_name"
      "investment_date"
      "is_agreement_confirmed"
    ]
    fid_start 12
    fid_end 14
    include_description 0
    key_variants {
     items [

     ]
    }
    field_name_variants {
      items [
      
      ]
    }
  }
}
