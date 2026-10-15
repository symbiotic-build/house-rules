<a id="scenario"></a>
# Scenario

A scenario connects concrete actions and caller-visible results across the sections that explain them.

It may link [requirement declarations](requirement-declaration.md#requirement-declaration) and [acceptance tests](acceptance-test.md#acceptance-test).
A tutorial does not become a test merely by describing behavior.
The manifest names whole [scenarios](scenario.md#scenario) for assignment.
Such assignments include every section containing their actions, requirements and linked tests.

Ordered steps must not silently serialize concurrent behavior.
A concurrent example names branches and synchronization points.
A completed competing action followed by submission is sequential.
