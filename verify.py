#!/usr/bin/python3

import base64

import algorithms
import rechnung
import verify_receipt

class DEPException(Exception):
    pass

class ChainingException(DEPException):
    def __init__(self, receipt, receiptPrev):
        super(ChainingException, self).__init__("At receipt \"" + receipt
                + "\": Previous receipt is not \"" + receiptPrev + "\".")

class NoRestoreReceiptAfterSignatureSystemFailureException(DEPException):
    def __init__(self, receipt):
        super(NoRestoreReceiptAfterSignatureSystemFailureException, self).__init__("At receipt \"" + receipt
                + "\": Receipt after restored signature system must not have any turnover.")

class InvalidTurnoverCounterException(rechnung.ReceiptException):
    def __init__(self, receipt):
        super(InvalidTurnoverCounterException, self).__init__(receipt, "Turnover counter invalid.")

class NoCertificateGivenException(DEPException):
    def __init__(self):
        super(NoCertificateGivenException, self).__init__("No certificate specified in DEP and multiple groups used.")

def verifyChain(receipt, prev, algorithm):
    chainingValue = algorithm.chain(receipt, prev)
    chainingValue = base64.b64encode(chainingValue)
    if chainingValue.decode("utf-8") != receipt.previousChain:
        raise ChainingException(receipt, prev)

def verifyCert(cert, chain):
    # TODO
    pass

def verifyGroup(group, lastReceipt, rv, lastTurnoverCounter, key):
    prev = lastReceipt
    prevObj = None
    if prev:
        prevObj, algorithmPrefix = rechnung.Rechnung.fromJWSString(prev)
    for r in group['Belege-kompakt']:
        ro = None
        algorithm = None
        try:
            ro, algorithm = rv.verifyJWS(r)
            if not prevObj or prevObj.isSignedBroken():
                if ro.sumA != 0.0 or ro.sumB != 0.0 or ro.sumC != 0.0 or ro.sumD != 0.0 or ro.sumE != 0.0:
                    raise NoRestoreReceiptAfterSignatureSystemFailureException(r)
        except verify_receipt.SignatureSystemFailedException as e:
            ro, algorithmPrefix = rechnung.Rechnung.fromJWSString(r)
            algorithm = algorithms.ALGORITHMS[algorithmPrefix]

        if not ro.isDummy():
            if key:
                newC = lastTurnoverCounter + int(round((ro.sumA + ro.sumB + ro.sumC + ro.sumD + ro.sumE) * 100))
                if not ro.isReversal():
                    turnoverCounter = ro.decryptTurnoverCounter(key, algorithm)
                    if turnoverCounter != newC:
                        print(newC)
                        print(turnoverCounter)
                        raise InvalidTurnoverCounterException(r)
                lastTurnoverCounter = newC

        verifyChain(ro, prev, algorithm)

        prev = r
        prevObj = ro

    return prev, lastTurnoverCounter

def verifyDEP(dep, keyStore, key):
    lastReceipt = None
    lastTurnoverCounter = 0

    if len(dep['Belege-Gruppe']) == 1 and not dep['Belege-Gruppe'][0]['Signaturzertifikat']:
        rv = verify_receipt.ReceiptVerifier.fromKeyStore(keyStore)
        lastReceipt, lastTurnoverCounter = verifyGroup(
                dep['Belege-Gruppe'][0], lastReceipt,
                rv, lastTurnoverCounter, key)
        return

    # TODO: check if all groups have certs or if there is just one group
    for group in dep['Belege-Gruppe']:
        cert = group['Signaturzertifikat']
        if not cert:
            raise NoCertificateGivenException()

        chain = group['Zertifizierungsstellen']
        verifyCert(cert, chain)
        rv = verify_receipt.ReceiptVerifier.fromDEPCert(cert)
    
        lastReceipt, lastTurnoverCounter = verifyGroup(group, lastReceipt,
                rv, lastTurnoverCounter, key)

import json
import sys

import key_store

if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: ./verify.py <dep export file> [<base64 AES key file>]")
        sys.exit(0)

    key = None
    if len(sys.argv) == 3:
        with open(sys.argv[2]) as f:
            key = base64.b64decode(f.read().encode("utf-8"))

    with open(sys.argv[1]) as f:
        verifyDEP(json.loads(f.read()), key_store.KeyStore(), key)
