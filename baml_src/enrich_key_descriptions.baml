// File: baml_src/enrich_key_descriptions.baml

// Output is a dictionary mapping key name → description
class KeyDescriptionPair {
  key string
  description string
}

// Output object wrapping list of key descriptions
class KeyDescriptionsOutput {
  descriptions KeyDescriptionPair[]
}

// The main function that generates human-friendly key descriptions
function GenerateKeyDescriptions(keys: string[]) -> KeyDescriptionsOutput {
  client BedrockClaude37Sonnet
  prompt #"
    You are a helpful assistant. Given a list of JSON keys from a form or document input, generate a human-readable description for each key that clearly explains what the field represents.

    If the meaning of any key is unclear or ambiguous, return "undefined" for that key.

    Try to enrich the descriptions — don't just reword the key. Include "who" or "what" where helpful.

    Retain numbering indicators in keys (e.g., `BOwnerCorporationFulllegalname4_ID` → this is the 4th full legal name of a building owner, etc.).

    For any field with the term “Inception Date”, **explicitly clarify** that it is not a Date of Birth.

    Keys:
    {{ keys }}

    Output:
    {{ ctx.output_format }}
  "#
}


test DescribeKeysTest {
  functions [GenerateKeyDescriptions]
  args {
    keys [
      "UserDOB"
      "PolicyInceptionDate"
      "BOwnerCorporationFulllegalname4_ID"
      "HasCriminalRecord"
      "Agent2Phone"
      "RandomField23"
    ]
  }
}
