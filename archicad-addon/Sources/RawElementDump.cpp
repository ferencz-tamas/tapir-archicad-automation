#include "RawElementDump.hpp"
#include "MigrationHelper.hpp"

// The field list (RawElementFields.inc) is generated from the AC28 DevKit by tools/gen_raw_dump_fields.py,
// so the real implementation is only compiled for Archicad 28; other versions get a stub.
#if defined (ServerMainVers_2800) && !defined (ServerMainVers_2900)
#define RAW_ELEMENT_DUMP_AVAILABLE
#include "RawElementFields.inc"

#include <cstdint>
#include <string>
#include <type_traits>

namespace {

template<typename T>
typename std::enable_if<std::is_same<T, bool>::value>::type AddRawValue (GS::ObjectState& os, const char* name, const T& value)
{
    os.Add (name, value);
}

template<typename T>
typename std::enable_if<std::is_floating_point<T>::value>::type AddRawValue (GS::ObjectState& os, const char* name, const T& value)
{
    os.Add (name, static_cast<double> (value));
}

template<typename T>
typename std::enable_if<(std::is_integral<T>::value && !std::is_same<T, bool>::value) || std::is_enum<T>::value>::type AddRawValue (GS::ObjectState& os, const char* name, const T& value)
{
    os.Add (name, static_cast<double> (static_cast<long long> (value)));
}

// Structs and arrays: little-endian hex of the raw bytes ("hex:0a000000") up to 32 bytes, otherwise a content hash
// ("hash:<fnv-1a 64> (<n> bytes)") - enough to see THAT a big member changed.
template<typename T>
typename std::enable_if<!std::is_arithmetic<T>::value && !std::is_enum<T>::value>::type AddRawValue (GS::ObjectState& os, const char* name, const T& value)
{
    static const char digits[] = "0123456789abcdef";
    const unsigned char* bytes = reinterpret_cast<const unsigned char*> (&value);
    std::string text;
    if constexpr (sizeof (T) <= 32) {
        text = "hex:";
        for (size_t i = 0; i < sizeof (T); ++i) {
            text += digits[bytes[i] >> 4];
            text += digits[bytes[i] & 0xF];
        }
    } else {
        std::uint64_t hash = 1469598103934665603ULL;
        for (size_t i = 0; i < sizeof (T); ++i) {
            hash = (hash ^ bytes[i]) * 1099511628211ULL;
        }
        text = "hash:";
        for (int shift = 60; shift >= 0; shift -= 4) {
            text += digits[(hash >> shift) & 0xF];
        }
        text += " (" + std::to_string (sizeof (T)) + " bytes)";
    }
    os.Add (name, GS::UniString (text.c_str ()));
}

// Unicode text members (zone name / number, ...)
template<size_t N>
void AddRawValue (GS::ObjectState& os, const char* name, const GS::uchar_t (&value)[N])
{
    os.Add (name, GS::UniString (value));
}

}

#define RAW_FIELD(name, member) AddRawValue (fields, name, member);
#endif

DumpRawElementFieldsCommand::DumpRawElementFieldsCommand () :
    CommandBase (CommonSchema::Used)
{
}

GS::String DumpRawElementFieldsCommand::GetName () const
{
    return "DumpRawElementFields";
}

GS::Optional<GS::UniString> DumpRawElementFieldsCommand::GetInputParametersSchema () const
{
    return R"({
        "type": "object",
        "properties": {
            "elementId": {
                "$ref": "#/ElementId"
            }
        },
        "additionalProperties": false
    })";
}

GS::Optional<GS::UniString> DumpRawElementFieldsCommand::GetRawResponseSchema () const
{
    return R"({
        "type": "object",
        "properties": {
            "type": {
                "type": "string"
            },
            "fields": {
                "type": "object",
                "description": "Every member of the raw API element struct by its native name (shared base structs flattened as openingBase.*/shellBase.*, union members as u.<member>.*). Numbers and booleans as such, texts as strings, small structs/arrays as little-endian hex (hex:...), big ones as a content hash (hash:...)."
            }
        },
        "additionalProperties": false,
        "required": [
            "type",
            "fields"
        ]
    })";
}

GS::ObjectState DumpRawElementFieldsCommand::Execute (const GS::ObjectState& parameters, GS::ProcessControl& /*processControl*/) const
{
#ifdef RAW_ELEMENT_DUMP_AVAILABLE
    API_Guid guid = APINULLGuid;
    const GS::ObjectState* elementId = parameters.Get ("elementId");
    if (elementId != nullptr) {
        guid = GetGuidFromObjectState (*elementId);
    } else {
        API_SelectionInfo selectionInfo;
        GS::Array<API_Neig> selectedNeigs;
        const GSErrCode selErr = ACAPI_Selection_Get (&selectionInfo, &selectedNeigs, false);
        if (selErr != NoError || selectedNeigs.IsEmpty ()) {
            return CreateErrorResponse (APIERR_BADPARS, "Pass an elementId or select an element.");
        }
        guid = selectedNeigs[0].guid;
    }

    API_Element elem = {};
    elem.header.guid = guid;
    const GSErrCode err = ACAPI_Element_Get (&elem);
    if (err != NoError) {
        return CreateErrorResponse (err, "Failed to get the element.");
    }

    const API_ElemTypeID typeID = GetElemTypeId (elem.header);

    GS::ObjectState fields;
    RAW_HEAD_FIELDS
    switch (typeID) {
        case API_WallID:         RAW_FIELDS_API_WallID         break;
        case API_ColumnID:       RAW_FIELDS_API_ColumnID       break;
        case API_BeamID:         RAW_FIELDS_API_BeamID         break;
        case API_WindowID:       RAW_FIELDS_API_WindowID       break;
        case API_DoorID:         RAW_FIELDS_API_DoorID         break;
        case API_ObjectID:       RAW_FIELDS_API_ObjectID       break;
        case API_LampID:         RAW_FIELDS_API_LampID         break;
        case API_SlabID:         RAW_FIELDS_API_SlabID         break;
        case API_RoofID:         RAW_FIELDS_API_RoofID         break;
        case API_MeshID:         RAW_FIELDS_API_MeshID         break;
        case API_ZoneID:         RAW_FIELDS_API_ZoneID         break;
        case API_CurtainWallID:  RAW_FIELDS_API_CurtainWallID  break;
        case API_ShellID:        RAW_FIELDS_API_ShellID        break;
        case API_MorphID:        RAW_FIELDS_API_MorphID        break;
        case API_SkylightID:     RAW_FIELDS_API_SkylightID     break;
        case API_StairID:        RAW_FIELDS_API_StairID        break;
        case API_RailingID:      RAW_FIELDS_API_RailingID      break;
        case API_OpeningID:      RAW_FIELDS_API_OpeningID      break;
        case API_DimensionID:    RAW_FIELDS_API_DimensionID    break;
        case API_LevelDimensionID:RAW_FIELDS_API_LevelDimensionID break;
        case API_RadialDimensionID:RAW_FIELDS_API_RadialDimensionID break;
        case API_AngleDimensionID:RAW_FIELDS_API_AngleDimensionID break;
        case API_TextID:         RAW_FIELDS_API_TextID         break;
        case API_LabelID:        RAW_FIELDS_API_LabelID        break;
        case API_LineID:         RAW_FIELDS_API_LineID         break;
        case API_ArcID:          RAW_FIELDS_API_ArcID          break;
        case API_CircleID:       RAW_FIELDS_API_CircleID       break;
        case API_PolyLineID:     RAW_FIELDS_API_PolyLineID     break;
        case API_SplineID:       RAW_FIELDS_API_SplineID       break;
        case API_PictureID:      RAW_FIELDS_API_PictureID      break;
        case API_DrawingID:      RAW_FIELDS_API_DrawingID      break;
        case API_HatchID:        RAW_FIELDS_API_HatchID        break;
        case API_HotspotID:      RAW_FIELDS_API_HotspotID      break;
        case API_CutPlaneID:     RAW_FIELDS_API_CutPlaneID     break;
        case API_ElevationID:    RAW_FIELDS_API_ElevationID    break;
        case API_InteriorElevationID:RAW_FIELDS_API_InteriorElevationID break;
        case API_DetailID:       RAW_FIELDS_API_DetailID       break;
        case API_WorksheetID:    RAW_FIELDS_API_WorksheetID    break;
        case API_CameraID:       RAW_FIELDS_API_CameraID       break;
        default:
            return CreateErrorResponse (APIERR_BADPARS, GS::UniString::Printf ("Element type %s is not supported yet.", GetElementTypeNonLocalizedName (typeID).ToCStr ().Get ()));
    }

    {   // the Info Box ID (memo)
        API_ElementMemo memo = {};
        const GS::OnExit guard ([&memo] () { ACAPI_DisposeElemMemoHdls (&memo); });
        ACAPI_Element_GetMemo (elem.header.guid, &memo, APIMemoMask_ElemInfoString);
        fields.Add ("memo.elemInfoString", memo.elemInfoString != nullptr ? *memo.elemInfoString : GS::EmptyUniString);
    }

    GS::ObjectState response;
    response.Add ("type", GetElementTypeNonLocalizedName (typeID));
    response.Add ("fields", fields);
    return response;
#else
    return CreateErrorResponse (APIERR_NOTSUPPORTED, "DumpRawElementFields is only available in the Archicad 28 build.");
#endif
}
