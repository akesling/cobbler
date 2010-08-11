##############################################################################
### Object Store Exceptions ##################################################

## Validation exceptions ####################################################


class CobblerValidationException(Exception):
    pass


class FileNotFound(CobblerValidationException):
    pass


class InvalidRequirement(CobblerValidationException):
    pass


class InvalidDefault(CobblerValidationException):
    pass


class InvalidValue(CobblerValidationException):
    pass


class InvalidChoice(CobblerValidationException):
    pass


class InvalidType(CobblerValidationException):
    pass


class InvalidItem(CobblerValidationException):
    pass


class InvalidFormat(CobblerValidationException):
    pass


## Handler Exceptions #######################################################


class CobblerHandlerException(Exception):
    pass


class InvalidSource(CobblerHandlerException):
    pass


class ItemNotFound(CobblerHandlerException):
    pass

class TypeNotFound(CobblerHandlerException):
    pass