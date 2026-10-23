class IdempotencyConflictError(Exception):
    pass


class TransactionNotFoundError(Exception):
    pass


class InvalidTransactionStatusError(Exception):
    pass


class PayFlowUnavailableError(Exception):
    pass


class PayFlowInvalidResponseError(Exception):
    pass


class PayFlowWebhookConflictError(Exception):
    pass
