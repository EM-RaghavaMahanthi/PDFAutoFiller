import fitz
import shutil
from src.utils.logger import logger
from src.utils.storage import save_file  


def bbox_match(bbox1, bbox2, tol=1):
    return all(abs(a - b) <= tol for a, b in zip(bbox1, bbox2))

def update_pdf_with_mapped_keys(pdf_path, final_flat_mapping, extracted_data, embed_pdf_path, storage_config, confidence_threshold=0.6):
    """
    Embed matched semantic keys into the PDF's field_name using fid-bbox lookup.
    """
    try:
        shutil.copy(pdf_path, embed_pdf_path)
        logger.info(f"Opened PDF copy for embedding: {embed_pdf_path} and original PDF is {pdf_path}")
        doc = fitz.open(pdf_path)

        fid_bbox_map = {}
        for page in extracted_data.get("pages", []):
            for field in page.get("form_fields", []):
                fid = str(field.get("fid"))
                bbox = field.get("bbox", {})
                page_num = field.get("page", 0) - 1  
                if bbox:
                    fid_bbox_map[fid] = (bbox, page_num)

        updated_count = 0
        cleared_count = 0

        # Clear all matching widget field_names first
        for fid, (bbox, page_num) in fid_bbox_map.items():
            target_bbox = tuple(int(bbox[k]) for k in ["left", "top", "right", "bottom"])
            page = doc[page_num]
            for widget in page.widgets():
                rect = widget.rect
                widget_bbox = (int(rect.x0), int(rect.y0), int(rect.x1), int(rect.y1))
                if bbox_match(widget_bbox, target_bbox):
                    widget.field_name = "unmapped"
                    widget.update()
                    cleared_count += 1

        # Apply matched keys with confidence threshold
        for fid, (matched_key, _, confidence) in final_flat_mapping.items():
            if not matched_key or confidence < confidence_threshold:
                continue
            if fid not in fid_bbox_map:
                logger.info(f"No bbox found for fid {fid} in extracted data.")
                continue

            bbox, page_num = fid_bbox_map[fid]
            target_bbox = tuple(int(bbox[k]) for k in ["left", "top", "right", "bottom"])
            page = doc[page_num]

            for widget in page.widgets():
                rect = widget.rect
                widget_bbox = (int(rect.x0), int(rect.y0), int(rect.x1), int(rect.y1))
                if bbox_match(widget_bbox, target_bbox):
                    widget.field_name = matched_key
                    widget.update()
                    updated_count += 1
                    break

        doc.save(embed_pdf_path)
        save_file(embed_pdf_path, storage_config,key_name="embed_pdf_path")
        logger.info(f"Cleared {cleared_count} field names.")
        logger.info(f"Successfully updated {updated_count} widgets with semantic keys.")
        logger.info(f"Embedded PDF saved at: {embed_pdf_path}")
        return fid_bbox_map

    except Exception as e:
        logger.error(f"Error embedding semantic keys into PDF: {e}")
