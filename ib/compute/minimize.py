import qcelemental
import qcengine
from openff.toolkit.topology.molecule import Molecule


def _minimize(molecule: Molecule, force_field: str) -> Molecule:
    if "openff" in force_field:
        basis = "smirnoff"
    elif "gaff" in force_field:
        basis = "antechamber"
    else:
        raise ValueError("Do not know what `basis` to use for this force field")

    return Molecule.from_qcschema(
        qcengine.compute_procedure(
            input_data=qcelemental.models.OptimizationInput(
                initial_molecule=molecule.to_qcschema(),
                input_specification={
                    "driver": "gradient",
                    "model": {
                        "method": force_field,
                        "basis": basis,
                    },
                },
                keywords={
                    "coordsys": "dlc",
                    "enforce": 0,
                    "epsilon": 1e-05,
                    "reset": True,
                    "qccnv": False,
                    "molcnv": False,
                    "check": 0,
                    "trust": 0.1,
                    "tmax": 0.3,
                    "maxiter": 300,
                    "convergence_set": "gau",
                    "program": "openmm",
                },
            ),
            procedure="geometric",
        ).final_molecule
    )
