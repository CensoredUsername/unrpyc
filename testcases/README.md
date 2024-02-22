The folders in this folder contain the following items:

* `originals`: contains several original .rpy files to be used in for testing the decompiler
* `compiled`: contains the compiled `.rpyc` files corresponding to the files in `originals`
* `expected`: contains the expected output of decompiling the `.rpyc` files to `.rpy` files

The contents in `expected` have been manually verified to match `originals`, as `.rpyc` files unfortunately do not contain enough data to reconstruct the original file perfectly.

To make this verification easier, a test script (`validate_expected.py`) has been provided that strips out comments and empty lines. Running it with the --update option will cause it to update the `expected` folder with decompiled `.rpy` files found in the `compiled` folder.

Licenses for the files can be found in the corresponding `originals` folder for each dataset.