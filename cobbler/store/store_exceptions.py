##############################################################################
### Object Store Exceptions ##################################################

## Validation exceptions ####################################################


class CobblerValidationException(Exception):
    pass


class InvalidRequirement(CobblerValidationException):
    pass


class InvalidDefault(CobblerValidationException):
    pass


class InvalidChoice(CobblerValidationException):
    pass


class TypeNotFound(CobblerValidationException):
    pass


class InvalidFormat(CobblerValidationException):
    pass


## Handler Exceptions #######################################################


class InvalidSource(CobblerValidationException):
    pass
