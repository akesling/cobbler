##############################################################################
### Object Store Exceptions ##################################################

class CobblerStoreException(Exception):
    pass

## Validation exceptions ####################################################


class CobblerValidationException(CobblerStoreException):
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


class CobblerHandlerException(CobblerStoreException):
    pass


class InvalidSource(CobblerHandlerException):
    pass


class ItemNotFound(CobblerHandlerException):
    pass

class TypeNotFound(CobblerHandlerException):
    pass
