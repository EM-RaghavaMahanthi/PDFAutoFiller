// File: baml_src/group.baml

// Schema for a grouped field
class FieldGroup {
  field_ids int[]         // List of field IDs (e.g. [29, 30])
  export_values string[]  // Labels like [Mr, Mrs]; empty if not radio
  description string      // Matched semantic key or generated group title
}


class GroupFieldsOutput {
  groups FieldGroup[]
}

class KeyDescription {
  key string
  descriptions string[]       
}

type KeyDescriptionList = KeyDescription[]




function GroupFieldsFromText(
  lines: string[],
  field_type: string,
  field_type_upper: string,
  field_type_lower: string,
  keys_data: KeyDescriptionList
) -> GroupFieldsOutput {
  client BedrockClaude37Sonnet
  prompt #"
    You are given lines extracted from a PDF form. Some lines contain tokens like [{{ field_type_upper  }}_FIELD:X], which represent individual {{field_type_lower }} fields.

    {% if keys_data %}
    You are also provided with a dictionary of semantic keys and their list of descriptions:
    {{ keys_data }}

    - For each group, if the group's context or label closely matches a description from this dictionary, use the corresponding key (the dictionary key, not the description) as the group’s description.
    - If no match is found, generate a new, crisp, context-driven description for the group as before.
    {% endif %}

    Your task is to:
    1. Group related {{field_type_lower }}s together.
    2. For each group, set only the numeric ID(s) from [{{ field_type_upper }}_FIELD:X] token.
    3. For each group, output:
       - field_ids: list of ints
       - export_values: list of string labels, if it's a radio group, else empty
       - description: semantic key or generated summary
    4. No explanation or extra text—return valid JSON only.

    {{ ctx.output_format }}

    Extracted lines to analyze:
    {% for line in lines %}
    {{ line }}
    {% endfor %}
  "#
}



test GroupFieldsTest {
  functions [GroupFieldsFromText]
  args {
    lines [
      "Title: [RADIO_FIELD:29] Mr"
      "Title: [RADIO_FIELD:30] Mrs"
      "Title: [RADIO_FIELD:31] Dr"
      "Consent: [RADIO_FIELD:45] yes"
      "Consent: [RADIO_FIELD:46] no"
    ]
    field_type "radio"
    field_type_upper "RADIO"
    field_type_lower "radio"
    keys_data [
      {
        key "name_title"
        descriptions [
          "Represents name prefixes like Mr, Mrs, Dr"
        ]
      }
      {
        key "consent"
        descriptions [
          "Indicates yes/no acceptance"
        ]
      }
    ]
  }
}


