class IdempotencyConflictError(Exception):
    pass


class TransactionNotFoundError(Exception):
    pass


class InvalidTransactionStatusError(Exception):
    pass
