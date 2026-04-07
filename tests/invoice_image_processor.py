"""
Invoice Image Processor using Docling with Granite-Docling-258M VLM

This script processes invoice images using the Granite-Docling-258M vision-language model.
Supports English, Arabic, French, Chinese, and Japanese (experimental).
"""

from docling.document_converter import DocumentConverter, ImageFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import VlmPipelineOptions
from docling.pipeline.vlm_pipeline import VlmPipeline
from pathlib import Path
import argparse


def process_invoice_image(image_path: str, output_dir: str = "output") -> None:
    """
    Process an invoice image using Docling with Granite-Docling-258M VLM model.
    
    Args:
        image_path: Path to the invoice image file
        output_dir: Directory to save the processed document (default: "output")
    """
    # Configure VLM pipeline with granite-docling model (default)
    pipeline_options = VlmPipelineOptions()
    
    # Initialize the document converter with VLM pipeline for images
    converter = DocumentConverter(
        format_options={
            InputFormat.IMAGE: ImageFormatOption(
                pipeline_options=pipeline_options,
                pipeline_cls=VlmPipeline,
            )
        }
    )
    
    # Convert the image path to Path object
    input_path = Path(image_path)
    
    # Validate input file exists
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {image_path}")
    
    # Validate file is an image
    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
    if input_path.suffix.lower() not in valid_extensions:
        raise ValueError(f"File must be an image. Supported formats: {', '.join(valid_extensions)}")
    
    print(f"Processing invoice image with Granite-Docling-258M VLM: {input_path.name}")
    print("Using multilingual model with Arabic, French, Chinese, and Japanese support...")
    
    # Process the image with Docling
    result = converter.convert(str(input_path))
    
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Export the document in different formats
    # Export as Markdown
    markdown_file = output_path / f"{input_path.stem}.md"
    with open(markdown_file, 'w', encoding='utf-8') as f:
        f.write(result.document.export_to_markdown())
    print(f"Exported to Markdown: {markdown_file}")
    
    # Export as JSON using the document's dict representation
    try:
        import json
        json_file = output_path / f"{input_path.stem}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(result.document.model_dump(), f, indent=2, ensure_ascii=False)
        print(f"Exported to JSON: {json_file}")
    except Exception as e:
        print(f"Warning: Could not export to JSON: {e}")
    
    # Export as plain text (using Markdown as fallback)
    try:
        text_file = output_path / f"{input_path.stem}.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            # Try to get text content, fallback to markdown
            try:
                f.write(result.document.export_to_text())
            except AttributeError:
                # Fallback to markdown if export_to_text doesn't exist
                f.write(result.document.export_to_markdown())
        print(f"Exported to Text: {text_file}")
    except Exception as e:
        print(f"Warning: Could not export to text: {e}")
    
    print(f"\nProcessing complete!")
    print(f"Used Granite-Docling-258M (258M parameters) for intelligent document understanding")
    print(f"Docling document object is ready: {type(result.document)}")
    
    return result.document


def main():
    """Main function to handle command-line interface."""
    parser = argparse.ArgumentParser(
        description="Process invoice images using Docling with Granite-Docling-258M VLM (supports Arabic, French, etc.)"
    )
    parser.add_argument(
        "image_path",
        type=str,
        help="Path to the invoice image file"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="output",
        help="Output directory for processed documents (default: output)"
    )
    
    args = parser.parse_args()
    
    try:
        process_invoice_image(args.image_path, args.output)
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
