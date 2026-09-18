class GridWiseError(Exception):
    """Errors with deliberately public, credential-free messages."""

    code = "internal_error"
    status_code = 500


class InterpretationError(GridWiseError):
    code = "interpretation_failed"


class InfeasibleScenario(GridWiseError):
    code = "infeasible_scenario"
    status_code = 422


class OptimizationError(GridWiseError):
    code = "optimization_failed"


class ReplayError(GridWiseError):
    code = "schedule_verification_failed"
