import os
import yaml
from src.core.pipeline import PDFProcessingPipeline
from src.utils.logger import logger

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

model_name = config["llm"]["model"]
provider = config["llm"]["provider"]
api_key_env = config["llm"]["api_key_env"]
api_key = config["llm"].get("api_key") or os.getenv(api_key_env)

if api_key:
    os.environ[api_key_env] = api_key
else:
    raise EnvironmentError(f"API key not found for {provider}. Check your config or environment variables.")

pdf_path = "data/input/sample1.pdf"
json_path = "data/input/sample1.json"
output_json = "data/temp/sample1_fitz_extracted_lines.json"
semantics_json = "data/temp/sample1_semantics.json"
mapped_json = "data/temp/sample1_mapped.json"

# Convert to absolute paths
pdf_path = os.path.abspath(pdf_path)
json_path = os.path.abspath(json_path)
output_json = os.path.abspath(output_json)
semantics_json = os.path.abspath(semantics_json)
mapped_json = os.path.abspath(mapped_json)

# Run pipeline
logger.info("Initializing PDF processing pipeline.")
pipeline = PDFProcessingPipeline(
    pdf_path=pdf_path,
    json_path=json_path,
    output_json=output_json,
    semantics_json=semantics_json,
    mapped_json=mapped_json,
    method="fitzl",
    semantic_method="prefix_suffix",
    model_name=model_name,
    provider=provider,
    api_key_env=api_key_env
)
pipeline.run_all()
logger.info("Pipeline execution completed successfully.")
