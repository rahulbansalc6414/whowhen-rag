# Security

Please report security problems privately through GitHub: **Security > Report a vulnerability** on this repository ([direct link](https://github.com/rahulbansalc6414/whowhen/security/advisories/new)). Do not open a public issue.

Relevant areas include SQL produced by `Filters.to_sql()` (column names are quoted and values are always parameters), prompt injection through user queries that changes the extracted filters, and handling of API keys.

Only the latest release receives fixes.
