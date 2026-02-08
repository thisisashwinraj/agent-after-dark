import logging
import warnings
from io import BytesIO
from dotenv import load_dotenv
from typing import Dict

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm 
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.platypus import Image, Paragraph, Table, TableStyle

from google.adk.tools.tool_context import ToolContext
from google.genai import types

load_dotenv()
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")
logger = logging.getLogger(__name__)


def _set_pdf_metadata(canvas, doc):
    canvas.setTitle("AI Generated Recipe")
    canvas.setAuthor("agent-after-dark")
    canvas.setSubject("Recipe generated from uploaded image")


async def generate_recipe_document(
    recipe_name: str,
    description: str,
    prep_time: str,
    serves: str,
    cook_time: str,
    ingredients: list[str],
    method: list[str],
    recipe_image_artifact_id: str,
    tool_context: ToolContext,
) -> Dict[str, str]:
    """
    Tool to generate a PDF version of a recipe and stores it as an ADK artifact.

    This tool takes markdown formatted recipe data along with a reference image 
    (provided via an artifact ID) and generates a well-formatted PDF document. 
    The generated PDF includes the recipe name, description, metadata, required 
    ingredients and preparation steps. The document is saved as an artifact and 
    can be retrieved using the returned artifact ID.

    Args:
        recipe_name (str): The title of the recipe.
        description (str): A short description or introduction to the recipe.
        prep_time (str): The preparation time required (e.g., "15 minutes").
        serves (str): Number of servings (e.g., "2 servings").
        cook_time (str): The cooking time required (e.g., "30 minutes").
        ingredients (list[str]): A list of ingredient strings.
        method (list[str]): A list of step-by-step cooking instructions.
        recipe_image_artifact_id (str): Artifact ID of the uploaded recipe image
            to be embedded in the PDF.
        tool_context (ToolContext): Context object used for loading and saving
            artifacts within the agent framework.

    Returns:
        Dict[str, str]: A dictionary containing:
            - status (str): Indicates the operation result.
                - "success" if the PDF was generated and stored successfully.
                - "error" if required inputs or artifacts are missing.
            - message (str): A short description of the result.
            - generated_file_artifact_id (str): Artifact ID of the generated PDF file
            (present only when status is "success").
    """
    WARNING_BG = colors.Color(1, 0.97, 0.80, alpha=0.9)

    if recipe_image_artifact_id is None:
        return {
            "status": "error",
            "message": "Recipe image artifact ID is missing."
        }

    recipe_image_artifact = await tool_context.load_artifact(
        filename=recipe_image_artifact_id
    )

    if recipe_image_artifact and recipe_image_artifact.inline_data:
        recipe_image_bytes = recipe_image_artifact.inline_data.data

    else:
        return {
            "status": "error",
            "message": "Recipe image artifact is missing inline data."
        }

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "title",
        fontSize=24,
        leading=28,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold"
    )

    meta_style = ParagraphStyle(
        "meta",
        fontSize=11,
        alignment=TA_CENTER,
        textColor=colors.black
    )

    section_title = ParagraphStyle(
        "section",
        fontSize=16,
        fontName="Helvetica-Bold",
        spaceAfter=8
    )

    body = ParagraphStyle(
        "body",
        fontSize=10.5,
        leading=14
    )

    story = []

    hero_img = Image(BytesIO(recipe_image_bytes))

    hero_img.drawWidth = doc.width
    hero_img.drawHeight = hero_img.drawWidth * hero_img.imageHeight / hero_img.imageWidth

    story.append(hero_img)
    story.append(Spacer(1, 0.75 * cm))

    story.append(Paragraph(recipe_name, title_style))
    story.append(Spacer(1, 0.5 * cm))

    meta_table = Table(
        [[
            Paragraph(f"<b>Preperation Time:</b> {prep_time}", meta_style),
            Paragraph(f"<b>Serves:</b> {serves}", meta_style),
            Paragraph(f"<b>Cooking Time:</b> {cook_time}", meta_style),
        ]],
        colWidths=[doc.width / 3] * 3
    )

    meta_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    story.append(meta_table)
    story.append(Spacer(1, 0.6 * cm))

    story.append(Paragraph("Description", section_title))
    story.append(Spacer(1, 0.2 * cm))

    story.append(Paragraph(description, body))
    story.append(Spacer(1, 0.6 * cm))

    story.append(Paragraph("Ingredients", section_title))
    story.append(Spacer(1, 0.2 * cm))

    ingredient_paragraphs = []
    for item in ingredients:
        ingredient_paragraphs.append(Paragraph(f"• {item}", body))

    ingredients_block = Table(
        [[ingredient_paragraphs]],
        colWidths=[doc.width * 0.5]
    )
    ingredients_block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP")
    ]))

    side_img = Image(BytesIO(recipe_image_bytes))

    side_img.drawWidth = doc.width * 0.40
    side_img.drawHeight = side_img.drawWidth * side_img.imageHeight / side_img.imageWidth

    layout_table = Table(
        [[ingredients_block, side_img]],
        colWidths=[
            doc.width * 0.55,
            doc.width * 0.40
        ]
    )

    layout_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    story.append(layout_table)
    story.append(Spacer(1, 0.6 * cm))

    story.append(Paragraph("Preparation Steps", section_title))
    story.append(Spacer(1, 0.2 * cm))

    for i, step in enumerate(method, start=1):
        story.append(Paragraph(f"<b>Step {i}.</b> {step}", body))
        story.append(Spacer(1, 0.1 * cm))

    story.append(Spacer(1, 0.6 * cm))

    warning_text = """
    <b>Disclaimer:</b> This recipe is generated by an AI system for educational 
    purposes only. Please use your own judgment while cooking. Always follow 
    proper safety practices, check ingredient suitability and ensure correct 
    procedures. The authors/developers are not responsible for any outcome 
    resulting from the use of this recipe.
    """

    warning_paragraph = Paragraph(warning_text.strip(), ParagraphStyle(
        name="WarningStyle",
        fontSize=9.5,
        leading=13,
        textColor=colors.black,
    ))

    warning_table = Table(
        [[warning_paragraph]],
        colWidths=[doc.width]
    )

    warning_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WARNING_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    story.append(warning_table)

    doc.build(
        story,
        onFirstPage=_set_pdf_metadata,
        onLaterPages=_set_pdf_metadata
    )

    buffer.seek(0)
    pdf_bytes = buffer.read()

    recipe_artifact = types.Part.from_bytes(
        data=pdf_bytes,
        mime_type="application/pdf"
    )

    artifact_id = f"{recipe_name.lower().replace(' ', '_')}_recipe.pdf"

    await tool_context.save_artifact(
        filename=artifact_id,
        artifact=recipe_artifact
    )

    return {
        "status": "success",
        "message": "Recipe document generated successfully.",
        "generated_file_artifact_id": artifact_id
    }
