// Learn more about clients at https://docs.boundaryml.com/docs/snippets/clients/overview

client<llm> CustomGPT4o {
  provider openai
  options {
    model "gpt-4o"
    api_key env.OPENAI_API_KEY
  }
}

client<llm> CustomGPT4oMini {
  provider openai
  retry_policy Exponential
  options {
    model "gpt-4o-mini"
    api_key env.OPENAI_API_KEY
  }
}

client<llm> BedrockClaude37Sonnet {
  provider aws-bedrock
  retry_policy BedrockExponential
  options {
    model "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    region "us-east-2"
    profile "default"
    inference_configuration {
      max_tokens 20000
      temperature 0.0
    }
  }
}


client<llm> BedrockClaude40Sonnet {
  provider aws-bedrock
  retry_policy BedrockExponential
  options {
    model "us.anthropic.claude-4-sonnet-20250522-v1:0"   
    region "us-east-2"
    profile "default"
    inference_configuration {
      max_tokens 20000
      temperature 0.0
    }
  }
}


client<llm> CustomSonnet {
  provider anthropic
  options {
    model "claude-3-5-sonnet-20241022"
    api_key env.ANTHROPIC_API_KEY
  }
}


client<llm> CustomHaiku {
  provider anthropic
  retry_policy Constant
  options {
    model "claude-3-haiku-20240307"
    api_key env.ANTHROPIC_API_KEY
  }
}

// https://docs.boundaryml.com/docs/snippets/clients/round-robin
client<llm> CustomFast {
  provider round-robin
  options {
    // This will alternate between the two clients
    strategy [CustomGPT4oMini, CustomHaiku]
  }
}

// https://docs.boundaryml.com/docs/snippets/clients/fallback
client<llm> OpenaiFallback {
  provider fallback
  options {
    // This will try the clients in order until one succeeds
    strategy [CustomGPT4oMini, CustomGPT4oMini]
  }
}

// https://docs.boundaryml.com/docs/snippets/clients/retry
retry_policy Constant {
  max_retries 3
  // Strategy is optional
  strategy {
    type constant_delay
    delay_ms 200
  }
}

retry_policy Exponential {
  max_retries 2
  // Strategy is optional
  strategy {
    type exponential_backoff
    delay_ms 300
    multiplier 1.5
    max_delay_ms 10000
  }
}

retry_policy BedrockExponential {
  max_retries 3
  strategy {
    type exponential_backoff
    delay_ms 300          
    multiplier 2.0       
    max_delay_ms 10000    
  }
}

retry_policy BedrockConstant {
  max_retries 3
  strategy {
    type constant_delay
    delay_ms 500          
  }
}