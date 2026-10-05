#pragma once

#include "CommandBase.hpp"

// Developer-only: dumps every member of the element's raw API struct (API_WallType, ...) by its native name.
class DumpRawElementFieldsCommand : public CommandBase
{
public:
    DumpRawElementFieldsCommand ();
    virtual GS::String GetName () const override;
    virtual GS::Optional<GS::UniString> GetInputParametersSchema () const override;
    virtual GS::Optional<GS::UniString> GetRawResponseSchema () const override;
    virtual GS::ObjectState Execute (const GS::ObjectState& parameters, GS::ProcessControl& processControl) const override;
};
