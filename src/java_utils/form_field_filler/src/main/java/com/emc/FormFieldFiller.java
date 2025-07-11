package com.emc;

import com.itextpdf.text.pdf.AcroFields;
import com.itextpdf.text.pdf.PdfReader;
import com.itextpdf.text.pdf.PdfStamper;

import java.io.FileOutputStream;
import java.util.Map;
import java.util.Set;
import java.util.List;
import java.util.ArrayList;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import java.lang.reflect.Type;
import java.io.FileReader;

public class FormFieldFiller {

    private Map<String, String> inputData;

    public FormFieldFiller(String inputJsonPath) throws Exception {
        this.inputData = loadInputData(inputJsonPath);
    }

    private Map<String, String> loadInputData(String inputJsonPath) throws Exception {
        Gson gson = new Gson();
        Type type = new TypeToken<Map<String, String>>(){}.getType();
        try (FileReader reader = new FileReader(inputJsonPath)) {
            return gson.fromJson(reader, type);
        }
    }

    public void fillPdf(String inputPdfPath, String outputPdfPath) throws Exception {
        PdfReader reader = new PdfReader(inputPdfPath);
        PdfStamper stamper = new PdfStamper(reader, new FileOutputStream(outputPdfPath));
        AcroFields form = stamper.getAcroFields();

        Set<String> fieldNames = form.getFields().keySet();

        // Separate fields by type
        List<String> textFields = new ArrayList<>();
        List<String> checkBoxes = new ArrayList<>();
        List<String> radioGroups = new ArrayList<>();

        for (String fieldName : fieldNames) {
            int fieldType = form.getFieldType(fieldName);
            switch (fieldType) {
                case AcroFields.FIELD_TYPE_CHECKBOX:
                    checkBoxes.add(fieldName);
                    break;
                case AcroFields.FIELD_TYPE_RADIOBUTTON:
                    radioGroups.add(fieldName);
                    break;
                case AcroFields.FIELD_TYPE_TEXT:
                    textFields.add(fieldName);
                    break;
                default:
                    // Ignore other types for now
                    break;
            }
        }

        fillTextFields(form, textFields);
        fillCheckBoxes(form, checkBoxes);
        fillRadioButtons(form, radioGroups);

        stamper.setFormFlattening(false); // Set to true to lock fields after filling
        stamper.close();
        reader.close();
    }

    private void fillTextFields(AcroFields form, List<String> textFields) throws Exception {
        for (String fieldName : textFields) {
            if (inputData.containsKey(fieldName)) {
                String value = inputData.get(fieldName);
                if (value != null) {
                    form.setField(fieldName, value);
                }
            }
        }
    }

    private void fillCheckBoxes(AcroFields form, List<String> checkBoxes) throws Exception {
        for (String fieldName : checkBoxes) {
            if (inputData.containsKey(fieldName)) {
                String value = inputData.get(fieldName);
                if (value != null) {
                    if (value.equalsIgnoreCase("yes") || value.equalsIgnoreCase("true") ||
                        value.equals("1") || value.equalsIgnoreCase("on")) {
                        form.setField(fieldName, "On");
                    } else {
                        form.setField(fieldName, "Off");
                    }
                }
            }
        }
    }

    private void fillRadioButtons(AcroFields form, List<String> radioGroups) throws Exception {
        for (String groupName : radioGroups) {
            if (inputData.containsKey(groupName)) {
                String value = inputData.get(groupName);
                if (value != null) {
                    // The value must match the export value of the radio button option
                    form.setField(groupName, value);
                }
            }
        }
    }

    // Main method for command-line usage
    public static void main(String[] args) {
        if (args.length != 3) {
            System.err.println("Usage: java FormFieldFiller <input-pdf> <input-json> <output-pdf>");
            System.exit(1);
        }

        String inputPdf = args[0];
        String inputJson = args[1];
        String outputPdf = args[2];

        try {
            FormFieldFiller filler = new FormFieldFiller(inputJson);
            filler.fillPdf(inputPdf, outputPdf);
            System.out.println("PDF form filled successfully: " + outputPdf);
        } catch (Exception e) {
            e.printStackTrace();
            System.err.println("Failed to fill PDF form: " + e.getMessage());
            System.exit(1);
        }
    }
}

