import mobase
from .profile_checker import ProfileCheckerPlugin

def createPlugin() -> mobase.IPlugin:
    return ProfileCheckerPlugin()
