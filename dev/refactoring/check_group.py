# FUNCTIONS


def assert_checks(results: list) -> None:
    for name, ok in results:
        print(('PASS: ' if ok else 'FAIL: ') + name)
    failed = [name for name, ok in results if not ok]
    print(f'{len(results) - len(failed)}/{len(results)} passed')
    if failed:
        raise AssertionError('failed checks: ' + '; '.join(failed))
