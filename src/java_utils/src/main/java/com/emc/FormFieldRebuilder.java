package com.emc;

import com.google.gson.*;
import com.itextpdf.text.Rectangle;
import com.itextpdf.text.pdf.*;

import java.io.FileReader;
import java.io.FileOutputStream;
import java.util.*;
import java.util.stream.Collectors;

public class FormFieldRebuilder {

    public static class FieldMeta {
        public String fid;
        public String matchedKey;
        public String value;
        public int type;
        public int page;
        public Rectangle rect;
        public String groupName;       // Used for radio buttons
        public String exportValue;     // The currently selected value for radio buttons
        public List<String> exportOptions; // All options in the radio group

        public FieldMeta(String value, int type, int page, Rectangle rect) {
            this.value = value;
            this.type = type;
            this.page = page;
            this.rect = rect;
            this.exportOptions = new ArrayList<>();
        }

        public FieldMeta(String value, int type, int page, Rectangle rect, String groupName, String exportValue, List<String> exportOptions) {
            this(value, type, page, rect);
            this.groupName = groupName;
            this.exportValue = exportValue;
            this.exportOptions = exportOptions != null ? exportOptions : new ArrayList<>();
        }
    }

    public static class FidMeta {
        public String fid;
        public int page;
        public Rectangle rect;

        public FidMeta(String fid, int page, Rectangle rect) {
            this.fid = fid;
            this.page = page;
            this.rect = rect;
        }
    }

    public static boolean rectsAreClose(Rectangle r1, Rectangle r2) {
        float threshold = 2.0f;

        return Math.abs(r1.getLeft() - r2.getLeft()) < threshold &&
                Math.abs(r1.getRight() - r2.getRight()) < threshold &&
                Math.abs(r1.getTop() - r2.getTop()) < threshold &&
                Math.abs(r1.getBottom() - r2.getBottom()) < threshold;
    }

    public static List<FidMeta> loadFidMeta(String jsonPath, PdfReader reader) throws Exception {
        List<FidMeta> result = new ArrayList<>();
        JsonObject obj = JsonParser.parseReader(new FileReader(jsonPath)).getAsJsonObject();
    
        JsonArray pages = obj.getAsJsonArray("pages");
        for (JsonElement pageEl : pages) {
            JsonObject pageObj = pageEl.getAsJsonObject();
            int page = pageObj.get("page_number").getAsInt();
    
            float pageHeight = reader.getPageSize(page).getHeight(); // Get iText page height
    
            JsonArray fields = pageObj.getAsJsonArray("form_fields");
            for (JsonElement fieldEl : fields) {
                JsonObject fieldObj = fieldEl.getAsJsonObject();
                String fid = fieldObj.get("fid").getAsString();
    
                JsonObject bbox = fieldObj.getAsJsonObject("bbox");
                float x0 = bbox.get("left").getAsFloat();
                float y0 = pageHeight - bbox.get("top").getAsFloat();      // Flip Y
                float x1 = bbox.get("right").getAsFloat();
                float y1 = pageHeight - bbox.get("bottom").getAsFloat();   // Flip Y
    
                Rectangle rect = new Rectangle(Math.round(x0), Math.round(y0), Math.round(x1), Math.round(y1));
                result.add(new FidMeta(fid, page, rect));
            }
        }
    
        System.out.println("✅ Loaded and normalized fid metadata for iText comparison.");
        return result;
    }
    

    public static Map<String, String> loadFidToKeyMap(String jsonPath) throws Exception {
        Map<String, String> map = new HashMap<>();
        JsonObject obj = JsonParser.parseReader(new FileReader(jsonPath)).getAsJsonObject();
    
        for (Map.Entry<String, JsonElement> entry : obj.entrySet()) {
            JsonArray arr = entry.getValue().getAsJsonArray();
    
            if (arr.size() < 3 || arr.get(0).isJsonNull() || arr.get(2).isJsonNull()) {
                //System.out.println("⚠️ Skipping mapping for key: " + entry.getKey() + " due to null or missing values.");
                continue;
            }
    
            String matchedKey = arr.get(0).getAsString();
            float confidence = arr.get(2).getAsFloat();
    
            if (confidence >= 0.7) {
                map.put(entry.getKey(), matchedKey);
            }
        }
    
        return map;
    }

    public static void renameFields(List<FieldMeta> metas, List<FidMeta> fids, Map<String, String> fidToKeyMap) {
        for (FieldMeta meta : metas) {
            for (FidMeta f : fids) {
                if (f.page == meta.page && rectsAreClose(f.rect, meta.rect)) {
                    String matchedKey = fidToKeyMap.getOrDefault(f.fid, "unmapped_" + f.fid);
                    //System.out.println("🔄 Matched fid: " + f.fid + " to field with rect " + meta.rect);
                    meta.fid = f.fid;
                    meta.groupName = matchedKey;
                    break;
                }
            }
            if (meta.groupName == null) {
                //System.out.println("⚠️  No fid matched for field at page " + meta.page + " rect: " + meta.rect);
                meta.groupName = "unmapped_unknown";
            }
        }
    }

    // These would hook into your existing remove/add logic
    public static void removeAllFields(String inputPdf, String outputPdf) throws Exception {
        PdfReader reader = new PdfReader(inputPdf);
        PdfStamper stamper = new PdfStamper(reader, new FileOutputStream(outputPdf));
        AcroFields form = stamper.getAcroFields();
        Map<String, AcroFields.Item> fields = form.getFields();
    
        for (Map.Entry<String, AcroFields.Item> entry : fields.entrySet()) {
            AcroFields.Item item = entry.getValue();
            int widgetCount = item.size();
    
            for (int i = 0; i < widgetCount; i++) {
                PdfDictionary widget = item.getWidget(i);
                int pageNum = item.getPage(i);
    
                PdfDictionary pageDict = reader.getPageN(pageNum);
                PdfArray annots = pageDict.getAsArray(PdfName.ANNOTS);
                if (annots != null) {
                    for (int j = 0; j < annots.size(); j++) {
                        PdfObject obj = annots.getPdfObject(j);
                        if (obj != null && obj.equals(widget)) {
                            annots.remove(j);
                            pageDict.put(PdfName.ANNOTS, annots); // 🆕 Put it back
                            break;
                        }
                    }
                }
    
                // Clean all possible metadata
                widget.remove(PdfName.T);       // field name
                widget.remove(PdfName.V);       // value
                widget.remove(PdfName.FT);      // field type
                widget.remove(PdfName.PARENT);  // hierarchy
                widget.remove(PdfName.SUBTYPE); // subtype
                widget.remove(PdfName.AS);      // 🆕 appearance state
                widget.remove(PdfName.AP);      // 🆕 appearance dictionary
            }
        }
    
        // Also remove AcroForm definitions
        PdfDictionary catalog = reader.getCatalog();
        PdfDictionary acroForm = catalog.getAsDict(PdfName.ACROFORM);
        if (acroForm != null) {
            acroForm.remove(PdfName.FIELDS);
            acroForm.remove(PdfName.NEEDAPPEARANCES);
        }
    
        stamper.close();
        reader.close();
        System.out.println("✅ All form fields and widgets removed.");
    }

    public static void addFields(String inputPdf, String outputPdf, List<FieldMeta> fields) throws Exception {
        PdfReader reader = new PdfReader(inputPdf);
        PdfStamper stamper = new PdfStamper(reader, new FileOutputStream(outputPdf));
        PdfWriter writer = stamper.getWriter();
    
        Map<FieldMeta, String> assignedNames = assignFieldNames(fields);
        Map<String, List<FieldMeta>> radioGroups = new LinkedHashMap<>();
        Map<String, List<FieldMeta>> textGroups = new LinkedHashMap<>();
        List<FieldMeta> checkboxes = new ArrayList<>();
    
        classifyFields(fields, assignedNames, radioGroups, textGroups, checkboxes);
    
        addRadioGroups(radioGroups, writer, stamper);
        addGroupedTextFields(textGroups, writer, stamper);
        addCheckboxes(checkboxes, assignedNames, writer, stamper);
    
        stamper.setFormFlattening(false);
        stamper.close();
        reader.close();
        System.out.println("🎯 All fields added and desynced using groupName + fid logic.");
    }
    
    private static Map<FieldMeta, String> assignFieldNames(List<FieldMeta> fields) {
        Map<FieldMeta, String> nameMap = new HashMap<>();
        for (FieldMeta meta : fields) {
            String key = (meta.groupName != null && !meta.groupName.isEmpty()) 
                ? meta.groupName 
                : "unmapped_" + (meta.fid != null ? meta.fid : UUID.randomUUID());
            nameMap.put(meta, key);
        }
        return nameMap;
    }
    
    private static void classifyFields(List<FieldMeta> fields, Map<FieldMeta, String> assignedNames,
                                       Map<String, List<FieldMeta>> radioGroups,
                                       Map<String, List<FieldMeta>> textGroups,
                                       List<FieldMeta> checkboxes) {
        for (FieldMeta meta : fields) {
            String name = assignedNames.get(meta);
            if (meta.type == AcroFields.FIELD_TYPE_RADIOBUTTON) {
                radioGroups.computeIfAbsent(name, k -> new ArrayList<>()).add(meta);
            } else if (meta.type == AcroFields.FIELD_TYPE_TEXT) {
                textGroups.computeIfAbsent(name, k -> new ArrayList<>()).add(meta);
            } else if (meta.type == AcroFields.FIELD_TYPE_CHECKBOX) {
                checkboxes.add(meta);
            }
        }
    }
    
    private static void addRadioGroups(Map<String, List<FieldMeta>> radioGroups, PdfWriter writer, PdfStamper stamper) throws Exception {
        for (Map.Entry<String, List<FieldMeta>> entry : radioGroups.entrySet()) {
            String name = entry.getKey();
            List<FieldMeta> group = entry.getValue();
    
            PdfFormField radioGroup = PdfFormField.createRadioButton(writer, true);
            radioGroup.setFieldName(name);
    
            for (FieldMeta meta : group) {
                RadioCheckField radio = new RadioCheckField(writer, meta.rect, null, meta.exportValue);
                radio.setCheckType(RadioCheckField.TYPE_SQUARE);
                PdfFormField radioField = radio.getRadioField();
    
                PdfDictionary apDict = new PdfDictionary();
                PdfDictionary ap = new PdfDictionary();
    
                PdfAppearance off = PdfAppearance.createAppearance(writer, meta.rect.getWidth(), meta.rect.getHeight());
                ap.put(PdfName.Off, off.getIndirectReference());
    
                for (String option : meta.exportOptions) {
                    PdfAppearance on = PdfAppearance.createAppearance(writer, meta.rect.getWidth(), meta.rect.getHeight());
                    on.setGrayFill(0.0f);
                    on.rectangle(2, 2, meta.rect.getWidth() - 4, meta.rect.getHeight() - 4);
                    on.fill();
                    ap.put(new PdfName(option), on.getIndirectReference());
                }
    
                apDict.put(PdfName.N, ap);
                radioField.put(PdfName.AP, apDict);
                radioField.put(PdfName.AS, PdfName.Off);
                radioGroup.addKid(radioField);
    
                System.out.println("🔘 Added radio option '" + meta.exportValue + "' for group: " + name);
            }
    
            radioGroup.put(PdfName.V, PdfName.Off);
            radioGroup.put(PdfName.AS, PdfName.Off);
            stamper.addAnnotation(radioGroup, group.get(0).page);
            System.out.println("✅ Added radio group '" + name + "' on page " + group.get(0).page);
        }
    }
    
    private static void addGroupedTextFields(Map<String, List<FieldMeta>> textGroups, PdfWriter writer, PdfStamper stamper) throws Exception {
        for (Map.Entry<String, List<FieldMeta>> entry : textGroups.entrySet()) {
            String name = entry.getKey();
            List<FieldMeta> group = entry.getValue();

            PdfFormField parent = PdfFormField.createTextField(writer, false, false, 100);
            parent.setFieldName(name);

            for (FieldMeta meta : group) {
                TextField tf = new TextField(writer, meta.rect, null);
                tf.setText(meta.value != null ? meta.value : "");
                PdfFormField widget = tf.getTextField();

                // 🔧 Fix: Explicitly place the widget on the correct page
                widget.setPlaceInPage(meta.page);

                parent.addKid(widget);
                System.out.println("📝 Grouped widget added for '" + name + "' on page " + meta.page);
            }

            // ⚠️ Important: Add parent field to *all* pages where kids are placed
            Set<Integer> uniquePages = group.stream().map(f -> f.page).collect(Collectors.toSet());
            for (int page : uniquePages) {
                stamper.addAnnotation(parent, page);
            }
        }
    }

    
    private static void addCheckboxes(List<FieldMeta> checkboxes, Map<FieldMeta, String> assignedNames, PdfWriter writer, PdfStamper stamper) throws Exception {
        for (FieldMeta meta : checkboxes) {
            String name = assignedNames.getOrDefault(meta, "unmapped_" + meta.fid);
            RadioCheckField checkbox = new RadioCheckField(writer, meta.rect, name, "Yes");
            checkbox.setCheckType(RadioCheckField.TYPE_CHECK);
            checkbox.setChecked("Yes".equalsIgnoreCase(meta.value));
            PdfFormField cb = checkbox.getCheckField();
            cb.setPlaceInPage(meta.page);
    
            stamper.addAnnotation(cb, meta.page);
            System.out.println("☑️ Checkbox field added: " + name + " on page " + meta.page);
        }
    }
    
    
    
    

    public static List<FieldMeta> extractFieldMetadata(String inputPdf) throws Exception {
        List<FieldMeta> fieldMetaList = new ArrayList<>();

        PdfReader reader = new PdfReader(inputPdf);
        AcroFields form = reader.getAcroFields();
        Map<String, AcroFields.Item> fields = form.getFields();

        for (Map.Entry<String, AcroFields.Item> entry : fields.entrySet()) {
            String fieldName = entry.getKey();
            AcroFields.Item item = entry.getValue();
            int type = form.getFieldType(fieldName);
            int widgetCount = item.size();

            for (int i = 0; i < widgetCount; i++) {
                PdfArray rectArray = item.getWidget(i).getAsArray(PdfName.RECT);
                if (rectArray == null || rectArray.size() != 4) continue;

                float x0 = rectArray.getAsNumber(0).floatValue();
                float y0 = rectArray.getAsNumber(1).floatValue();
                float x1 = rectArray.getAsNumber(2).floatValue();
                float y1 = rectArray.getAsNumber(3).floatValue();
                Rectangle rect = new Rectangle(x0, y1, x1, y0);
                int page = item.getPage(i);

                if (type == AcroFields.FIELD_TYPE_RADIOBUTTON) {
                    PdfDictionary widget = item.getWidget(i);
                    PdfDictionary ap = widget.getAsDict(PdfName.AP);
                    PdfDictionary normal = ap != null ? ap.getAsDict(PdfName.N) : null;
                    List<String> options = new ArrayList<>();
                    if (normal != null) {
                        for (PdfName key : normal.getKeys()) {
                            String opt = key.toString().replaceFirst("/", "");
                            if (!options.contains(opt)) {
                                options.add(opt);
                            }
                        }
                    }
                    PdfDictionary merged = item.getMerged(i);
                    PdfName as = merged.getAsName(PdfName.AS);
                    String exportValue = (as != null) ? as.toString().replaceFirst("/", "") : "";
                    String selectedValue = form.getField(fieldName);
                    fieldMetaList.add(new FieldMeta(selectedValue, type, page, rect, fieldName, exportValue, options));
                } else {
                    String value = form.getField(fieldName);
                    fieldMetaList.add(new FieldMeta(value, type, page, rect));
                }
            }
        }

        reader.close();
        return fieldMetaList;
    }

    public static void rebuildForm(String original, String extractedJson, String mappingJson, String rebuilt) throws Exception {
        String cleaned = original.replace(".pdf", ".cleaned.pdf");
    
        PdfReader reader = new PdfReader(original);
        List<FidMeta> fidMetaList = loadFidMeta(extractedJson, reader);
        Map<String, String> fidToKeyMap = loadFidToKeyMap(mappingJson);
        List<FieldMeta> fields = extractFieldMetadata(original);
    
        renameFields(fields, fidMetaList, fidToKeyMap);
        removeAllFields(original, cleaned);
        addFields(cleaned, rebuilt, fields);
    }
    
    public static void main(String[] args) throws Exception {
        if (args.length != 4) {
            System.err.println("Usage: java -jar FormFieldRebuilder.jar <original.pdf> <extracted.json> <mapping.json> <rebuilt.pdf>");
            System.exit(1);
        }
    
        rebuildForm(args[0], args[1], args[2], args[3]);
    }

}