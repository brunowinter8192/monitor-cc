# INFRASTRUCTURE

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"

# FUNCTIONS

def check(label, condition):
    print(f"  {'  '+_PASS if condition else '  '+_FAIL}  {label}")
    return condition
