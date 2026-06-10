# Smoke Evidence

Run from the pack build root:

```sh
python3 -m unittest discover -s tests
```

The tests create temporary `fable-disk/trace` data outside this repository and
verify:

- task scaffolding creates the required trace tree
- model detection records only Fable model ids by default
- empty STANDARD specs fail the spec gate
- context reads create context and observation events
