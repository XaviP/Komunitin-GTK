import sys, getpass

from utils.oauth2 import ApiAccess
from utils.api_services import get_account_info


def command_line_interface():
    user = ""
    access = ApiAccess()
    if not access.has_access:
        ok = False
        while not ok:
            user = access.user
            message_input = "User: (" + user + "): " if user else "User: "
            user_input = input(message_input)
            password = getpass.getpass()
            if user_input:
                user = user_input
            ok, error = access.new_access(user, password)
            if not ok:
                if error == "Wrong credentials":
                    print(error)
                if error[0:7] == "Network":
                    print(error)
                    sys.exit()

    print(get_account_info(access.headers))
