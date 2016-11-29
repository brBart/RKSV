#!/usr/bin/python3

from builtins import int

import base64
import enum

import key_store
import receipt
import verify

import run_test

class TestVerifyResult(enum.Enum):
    OK = 1
    FAIL = 2
    ERROR = 3

def testVerify(spec, pub, priv, closed):
    expected_exception_type = 'no Exception'
    expected_exception_receipt = None

    actual_exception_type = 'no Exception'
    actual_exception = None

    try:
        expected_exception_type = spec.get('expectedException',
                'no Exception')
        expected_exception_receipt = spec.get('exceptionReceipt')

        keymat = [(pub, priv)] * spec['numberOfSignatureDevices']
        key = base64.b64decode(spec['base64AesKey'])

        dep, cc = run_test.runTest(spec, keymat, closed)
        ks = key_store.KeyStore.readStoreFromJson(cc)

        verify.verifyDEP(dep, ks, key)
    except (receipt.ReceiptException, verify.DEPException) as e:
        actual_exception = e
    except Exception as e:
        return TestVerifyResult.ERROR, e

    if actual_exception:
        actual_exception_type = type(actual_exception).__name__

    if actual_exception_type != expected_exception_type:
        return TestVerifyResult.FAIL, Exception(
                'Expected "{}" but got "{}", message: "{}"'.format(
                    expected_exception_type, actual_exception_type,
                    actual_exception))

    if actual_exception and expected_exception_receipt:
        if actual_exception.receipt != expected_exception_receipt:
            return TestVerifyResult.FAIL, Exception(
                    'Expected "{}" at receipt "{}" but it occured at "{}" instead'.format(
                        expected_exception_type, expected_exception_receipt,
                        actual_exception.receipt))

    return TestVerifyResult.OK, None

def testVerifyMulti(specs, pub, priv, closed, tcDefaultSize):
    results = list()
    for s in specs:
        label = s.get('simulationRunLabel', 'Unknown')
        tc_size = s.get('turnoverCounterSize', tcDefaultSize)
        if label == 'Unknown':
            result = TestVerifyResult.ERROR
            msg = 'No run label'
        else:
            result, msg = testVerify(s, pub, priv, closed)
        results.append((label, closed, tc_size, result, msg))

    return results

def printTestVerifyResult(label, closed, tc_size, result, msg):
    open_str = 'closed' if closed else 'open'
    print('{: <30}({: >6}, {: >2})...'.format(label, open_str,
        tc_size), end='')
    print('{:.>5}'.format(result.name))
    if msg:
        print(msg)

import json
import sys

def usage():
    print("Usage: ./test_verify.py open <JSON test case spec> <cert priv> <cert> [<turnover counter size>]")
    print("       ./test_verify.py closed <JSON test case spec> <key priv> <pub key> [<turnover counter size>]")
    print("       ./test_verify.py multi <open|closed> <key priv> <pub key> <turnover counter size> <JSON test case spec 1>...")
    sys.exit(0)

if __name__ == "__main__":
    def closed_or_usage(arg):
        if arg == 'closed':
            return True
        elif arg == 'open':
            return False
        usage()

    def tc_size_or_error(arg):
        turnoverCounterSize = int(arg)
        if turnoverCounterSize < 5 or turnoverCounterSize > 16:
            print(_("Turnover counter size needs to be between 5 and 16."))
            sys.exit(0)
        return turnoverCounterSize

    def arg_read_file(arg):
        with open(arg) as f:
            return f.read()

    import gettext
    gettext.install('rktool', './lang', True)

    if len(sys.argv) < 5:
        usage()

    if sys.argv[1] == 'multi':
        if len(sys.argv) < 7:
            usage()

        closed = closed_or_usage(sys.argv[2])
        turnoverCounterSize = tc_size_or_error(sys.argv[5])

        pub = arg_read_file(sys.argv[4])
        priv = arg_read_file(sys.argv[3])

        specs = list()
        for tc in sys.argv[6:]:
            tcJson = json.loads(arg_read_file(tc))
            tcJson['turnoverCounterSize'] = turnoverCounterSize
            specs.append(tcJson)

        results = testVerifyMulti(specs, pub, priv, closed, 8)
        for r in results:
            printTestVerifyResult(*r)

        sys.exit(0)

    if len(sys.argv) > 6:
        usage()

    closed = closed_or_usage(sys.argv[1])

    tcJson = json.loads(arg_read_file(sys.argv[2]))

    if len(sys.argv) == 6:
        turnoverCounterSize = tc_size_or_error(sys.argv[5])
        tcJson['turnoverCounterSize'] = turnoverCounterSize

    pub = arg_read_file(sys.argv[4])
    priv = arg_read_file(sys.argv[3])

    test_name = tcJson['simulationRunLabel']
    tc_size = tcJson.get('turnoverCounterSize', 8)

    result, msg = testVerify(tcJson, pub, priv, closed)
    printTestVerifyResult(test_name, closed, tc_size, result, msg)
