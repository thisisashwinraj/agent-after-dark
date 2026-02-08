import os
import hashlib
import logging
import warnings
from dotenv import load_dotenv
from typing import List

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse, LlmRequest
from google.genai.types import Part

load_dotenv()
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")
logger = logging.getLogger(__name__)


async def _process_inline_data_part(
    part: Part,
    callback_context: CallbackContext
) -> List[Part]:
    filename = part.inline_data.display_name or "uploaded_image"
    image_data = part.inline_data.data

    hash_input = filename.encode("utf-8") + image_data
    content_hash = hashlib.sha256(hash_input).hexdigest()[:16]

    mime_type = part.inline_data.mime_type
    extension = mime_type.split("/")[-1]

    artifact_id = f"user_uploaded_img_{content_hash}.{extension}"

    if artifact_id not in await callback_context.list_artifacts():
        await callback_context.save_artifact(
            filename=artifact_id,
            artifact=part
        )

    artifact_description = f"""
    [User Uploaded Artifact]
    Below is the content of artifact ID : {artifact_id}
    """

    return [Part(text=artifact_description), part]


async def _process_function_response_part(
    part: Part, 
    callback_context: CallbackContext
) -> List[Part]:
    function_response_part = part.function_response.response
    artifact_id = function_response_part.get("tool_response_artifact_id")

    if not artifact_id:
        return [part]

    artifact = await callback_context.load_artifact(filename=artifact_id)

    artifact_description = f"""
    [Tool Response Artifact]
    Below is the content of artifact ID : {artifact_id}
    """

    return [part, Part(text=artifact_description), artifact]


async def before_model_callback(
    llm_request: LlmRequest,
    callback_context: CallbackContext
) -> LlmResponse | None:
    for content in llm_request.contents:
        if not content.parts: continue

        modified_parts = []
        for idx, part in enumerate(content.parts):
            if part.inline_data:
                processed_parts = await _process_inline_data_part(
                    part,
                    callback_context
                )

            elif part.function_response:
                if part.function_response.name in [
                    "generate_recipe_document"
                ]:
                    processed_parts = await _process_function_response_part(
                        part,
                        callback_context
                    )
                else:
                    processed_parts = [part]

            else:
                processed_parts = [part]

            modified_parts.extend(processed_parts)

        content.parts = modified_parts
