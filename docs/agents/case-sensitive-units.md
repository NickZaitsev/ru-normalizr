# Case-sensitive units

Keep case-insensitive aliases lowercase in `UNITS_DATA`. Put SI symbols whose
case changes their meaning (for example `мА` or `кА`) in
`CASE_SENSITIVE_UNITS_DATA`, and resolve input through `resolve_unit_info`.
Lowercasing those symbols directly would turn ordinary `ма`/`ка` tokens into
measurement units.
