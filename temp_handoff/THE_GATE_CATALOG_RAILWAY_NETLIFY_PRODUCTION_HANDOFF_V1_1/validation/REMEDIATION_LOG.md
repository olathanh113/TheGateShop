# Remediation log

1. Eight red-capable tests reproduced all four findings before source changes.
2. One implementation pass added dual-clock freshness, disabled-startup guard, safe Netlify merge and origin/topology documentation.
3. All eight targeted tests then passed; full source and clean staging suites passed 181/181.
4. A contract evidence one-liner initially expanded the literal JSON key `$schema` in the shell. The command was corrected using a literal-safe key expression; runtime/source was unchanged.

No test, TTL, assertion, guard, publication policy, auth rule, retention or generation-coherence rule was weakened.
