#!/usr/bin/env python2.7

"""
This module provides functions to verify a DEP.
"""
from builtins import int

import base64

import algorithms
import key_store
import receipt
import utils
import verify_receipt

class DEPException(Exception):
    """
    An exception that is thrown if something is wrong with a DEP.
    """

    pass

class DEPReceiptException(DEPException):
    """
    This exception indicates that an error was found in a DEP at a
    specific receipt.
    """

    def __init__(self, receipt, message):
        super(DEPReceiptException, self).__init__(
                _("At receipt \"{0}\": {1}").format(receipt, message))
        self.receipt = receipt

class ChainingException(DEPReceiptException):
    """
    This exception indicates that the chaining value in a receipt is invalid and
    that the chain of receipts can not be verified.
    """

    def __init__(self, rec, recPrev):
        super(ChainingException, self).__init__(rec,
                _("Previous receipt is not \"{0}\".").format(recPrev))

class NoRestoreReceiptAfterSignatureSystemFailureException(DEPReceiptException):
    """
    This exception indicates that, after a signature system is first used or
    after it has been repaired, no receipt with zero turnover was created as
    required.
    """

    def __init__(self, rec):
        super(NoRestoreReceiptAfterSignatureSystemFailureException, self).__init__(rec,
                _("Receipt after restored signature system must not have any turnover."))

class DuplicateReceiptIdException(DEPReceiptException):
    """
    This exception indicates that the ID of a receipt is already in use in
    a previous receipt.
    """

    def __init__(self, rec):
        super(DuplicateReceiptIdException, self).__init__(rec,
                _("Receipt ID already in use."))

class InvalidTurnoverCounterException(DEPReceiptException):
    """
    This exception indicates that the turnover counter is invalid.
    """

    def __init__(self, rec):
        super(InvalidTurnoverCounterException, self).__init__(rec,
                _("Turnover counter invalid."))

class ChangingRegisterIdException(DEPReceiptException):
    """
    This exception indicates that the register ID changed.
    """

    def __init__(self, rec):
        super(ChangingRegisterIdException, self).__init__(rec,
                _("Register ID changed."))

class DecreasingDateException(DEPReceiptException):
    """
    This exception indicates that the date on the receipt is lower than
    the date on the previous receipt.
    """

    def __init__(self, rec):
        super(DecreasingDateException, self).__init__(rec,
                _("Receipt was created before previous receipt."))

class ChangingSystemTypeException(DEPReceiptException):
    """
    This exception indicates that the type of the system (open/closed)
    changed.
    """

    def __init__(self, rec):
        super(ChangingSystemTypeException, self).__init__(rec,
                _("The system type changed."))

class ChangingTurnoverCounterSizeException(DEPReceiptException):
    """
    This exception indicates that the size of the turnover counter
    changed.
    """

    def __init__(self, rec):
        super(ChangingTurnoverCounterSizeException, self).__init__(rec,
                _("The size of the turnover counter changed."))

class NoCertificateGivenException(DEPException):
    """
    This exception indicates that a DEP using multiple receipt groups did not
    specify the used certificate for a group.
    """

    def __init__(self):
        super(NoCertificateGivenException, self).__init__(_("No certificate specified in DEP and multiple groups used."))

class UntrustedCertificateException(DEPException):
    """
    This exception indicates that neither the used certificate (or public key)
    nor any of the certificates in the certificate chain is available in the
    used key store.
    """

    def __init__(self, cert):
        super(UntrustedCertificateException, self).__init__(
                _("Certificate \"%s\" is not trusted.") % cert)

class CertificateChainBrokenException(DEPException):
    """
    This exception indicates that a given certificate chain is broken at
    the given certificate (i.e. the certificate was not properly signed
    by the next in the chain).
    """

    def __init__(self, cert, sign):
        super(CertificateChainBrokenException, self).__init__(
                _("Certificate \"{}\" was not signed by \"{}\".").format(
                    cert, sign))

class CertificateSerialCollisionException(DEPException):
    """
    This exception indicates that two certificates with matching serials but
    different fingerprints were detected which could indicate an attempted attack.
    """

    def __init__(self, serial, cert1FP, cert2FP):
        super(CertificateSerialCollisionException, self).__init__(
                _("Two certificates with serial \"{0}\" detected (fingerprints \"{1}\" and \"{2}\"). This may be an attempted attack.").format(
                    serial, cert1FP, cert2FP))

class SignatureSystemFailedOnInitialReceiptException(DEPReceiptException):
    """
    Indicates that the initial receipt was not signed.
    """
    def __init__(self, rec):
        super(SignatureSystemFailedOnInitialReceiptException, self).__init__(rec,
                _("Initial receipt not signed."))

class NonzeroTurnoverOnInitialReceiptException(DEPReceiptException):
    """
    Indicates that the initial receipt has a nonzero turnover.
    """
    def __init__(self, rec):
        super(NonzeroTurnoverOnInitialReceiptException, self).__init__(
                rec, _("Initial receipt has nonzero turnover."))

class InvalidChainingOnInitialReceiptException(DEPReceiptException):
    """
    Indicates that the initial receipt has not been chained to the cash
    register ID.
    """
    def __init__(self, rec):
        super(InvalidChainingOnInitialReceiptException, self).__init__(
                rec,
                _("Initial receipt has not been chained to the cash register ID."))

class NonstandardTypeOnInitialReceiptException(DEPReceiptException):
    """
    Indicates that the initial receipt is a dummy or reversal receipt.
    """
    def __init__(self, rec):
        super(NonstandardTypeOnInitialReceiptException, self).__init__(
                rec,
                _("Initial receipt is a dummy or reversal receipt."))

def verifyChain(rec, prev, algorithm):
    """
    Verifies that a receipt is preceeded by another receipt in the receipt
    chain. It returns nothing on success and throws an exception otherwise.
    :param rec: The new receipt as a receipt object.
    :param prev: The previous receipt as a JWS string.
    :param algorithm: The algorithm class to use.
    :throws: ChainingException
    :throws: InvalidChainingOnInitialReceiptException
    """
    chainingValue = algorithm.chain(rec, prev)
    chainingValue = base64.b64encode(chainingValue)
    if chainingValue.decode("utf-8") != rec.previousChain:
        if prev:
            raise ChainingException(rec.receiptId, prev)
        else:
            raise InvalidChainingOnInitialReceiptException(rec.receiptId)

def verifyCert(cert, chain, keyStore):
    """
    Verifies that a certificate or one of its signers is in the given key store.
    Returns nothing on success and throws an exception otherwise.
    :param cert: The certificate to verify as a PEM string without header and
    footer.
    :param chain: A list of certificates as PEM strings without header and
    footer. These represent the signing chain for the certificate.
    :param keyStore: The key store.
    :throws: UntrustedCertificateException
    :throws: CertificateSerialCollisionException
    :throws: CertificateChainBrokenException
    """
    prev = utils.loadCert(utils.addPEMCertHeaders(cert))
    first = prev

    for c in chain:
        ksCert = keyStore.getCert(key_store.numSerialToKeyId(prev.serial))
        if ksCert:
            if utils.certFingerprint(ksCert) != utils.certFingerprint(prev):
                raise CertificateSerialCollisionException(
                        key_store.numSerialToKeyId(prev.serial),
                        utils.certFingerprint(prev),
                        utils.certFingerprint(ksCert))
            return

        cur = utils.loadCert(utils.addPEMCertHeaders(c))

        if not utils.verifyCert(prev, cur):
            raise CertificateChainBrokenException(
                    key_store.numSerialToKeyId(prev.serial),
                    key_store.numSerialToKeyId(cur.serial))

        prev = cur

    ksCert = keyStore.getCert(key_store.numSerialToKeyId(prev.serial))
    if ksCert:
        if utils.certFingerprint(ksCert) != utils.certFingerprint(prev):
            raise CertificateSerialCollisionException(
                    key_store.numSerialToKeyId(prev.serial),
                    utils.certFingerprint(prev),
                    utils.certFingerprint(ksCert))
        return

    raise UntrustedCertificateException(key_store.numSerialToKeyId(
        first.serial))

class VerifyGroupState(object):
    def __init__(self):
        self.lastReceiptJWS = None
        self.lastTurnoverCounter = 0
        self.turnoverCounterSize = None
        self.usedReceiptIds = set()
        self.needRestoreReceipt = False

def verifyGroup(group, rv, key, state=None):
    """
    Verifies a group of receipts from a DEP. It checks if the signature of each
    receipt is valid, if the receipts are properly chained and if receipts with
    zero turnover are present as required. If a key is specified it also
    verifies the turnover counter. Returns the last receipt in the group and the
    last known value of the turnover counter on success and throws an exception
    otherwise.
    :param group: The receipt group as a json object.
    :param rv: The receipt verifier object used to verify single receipts.
    :param key: The key used to decrypt the turnover counter as a byte list or
    None.
    :param state: The state returned by a previous call to verifyGroup(), or
    None if this is the first group.
    :return: A state object containing the last receipt in the group as JWS
    string, the last known value of the turnover counter as int and the size of
    the encrypted base64 encoded turnover counter as int. This object should be
    passed to the next call to verifyGroup().
    :throws: NoRestoreReceiptAfterSignatureSystemFailure
    :throws: InvalidTurnoverCounterException
    :throws: CertSerialInvalidException
    :throws: CertSerialMismatchException
    :throws: NoPublicKeyException
    :throws: InvalidSignatureException
    :throws: ChainingException
    :throws: MalformedReceiptException
    :throws: UnknownAlgorithmException
    :throws: AlgorithmMismatchException
    :throws: SignatureSystemFailedOnInitialReceiptException
    :throws: UnsignedNullReceiptException
    :throws: NonzeroTurnoverOnInitialReceiptException
    :throws: InvalidChainingOnInitialReceiptException
    :throws: NonstandardTypeOnInitialReceiptException
    :throws: ChangingRegisterIdException
    :throws: DecreasingDateException
    :throws: ChangingSystemTypeException
    :throws: ChangingTurnoverCounterSizeException
    :throws: DuplicateReceiptIdException
    """
    if not state:
        state = VerifyGroupState()

    prev = state.lastReceiptJWS
    prevObj = None
    if prev:
        prevObj, algorithmPrefix = receipt.Receipt.fromJWSString(prev)
    for r in group['Belege-kompakt']:
        ro = None
        algorithm = None
        try:
            ro, algorithm = rv.verifyJWS(r)
            if prevObj and (not ro.isNull() or ro.isDummy() or ro.isReversal()):
                if state.needRestoreReceipt:
                    raise NoRestoreReceiptAfterSignatureSystemFailureException(ro.receiptId)
                if prevObj.isSignedBroken():
                    state.needRestoreReceipt = True
            else:
                state.needRestoreReceipt = False
        except verify_receipt.SignatureSystemFailedException as e:
            ro, algorithmPrefix = receipt.Receipt.fromJWSString(r)
            if not prevObj:
                raise SignatureSystemFailedOnInitialReceiptException(ro.receiptId)
            if state.needRestoreReceipt:
                raise NoRestoreReceiptAfterSignatureSystemFailureException(ro.receiptId)
            algorithm = algorithms.ALGORITHMS[algorithmPrefix]
        except verify_receipt.UnsignedNullReceiptException as e:
            ro, algorithmPrefix = receipt.Receipt.fromJWSString(r)
            if not prevObj:
                raise SignatureSystemFailedOnInitialReceiptException(ro.receiptId)
            raise e

        if not prevObj:
            if not ro.isNull():
                raise NonzeroTurnoverOnInitialReceiptException(ro.receiptId)
            if ro.isDummy() or ro.isReversal():
                raise NonstandardTypeOnInitialReceiptException(ro.receiptId)
            state.turnoverCounterSize = len(ro.encTurnoverCounter)
        else:
            if ro.receiptId in state.usedReceiptIds:
                raise DuplicateReceiptIdException(ro.receiptId)
            if prevObj.registerId != ro.registerId:
                raise ChangingRegisterIdException(ro.receiptId)
            if (prevObj.zda == 'AT0' and ro.zda != 'AT0') or (
                    prevObj.zda != 'AT0' and ro.zda == 'AT0'):
                raise ChangingSystemTypeException(ro.receiptId)
            # These checks are not necessary according to:
            # https://github.com/a-sit-plus/at-registrierkassen-mustercode/issues/144#issuecomment-255786335
            #if prevObj.dateTime > ro.dateTime:
            #    raise DecreasingDateException(ro.receiptId)
            #if not ro.isDummy() and not ro.isReversal() and len(
            #        ro.encTurnoverCounter) != state.turnoverCounterSize:
            #    raise ChangingTurnoverCounterSizeException(ro.receiptId)

        state.usedReceiptIds.add(ro.receiptId)

        if not ro.isDummy():
            if key:
                newC = state.lastTurnoverCounter + int(round(
                    (ro.sumA + ro.sumB + ro.sumC + ro.sumD + ro.sumE) * 100))
                if not ro.isReversal():
                    turnoverCounter = ro.decryptTurnoverCounter(key, algorithm)
                    if turnoverCounter != newC:
                        raise InvalidTurnoverCounterException(ro.receiptId)
                state.lastTurnoverCounter = newC

        verifyChain(ro, prev, algorithm)

        prev = r
        prevObj = ro

    state.lastReceiptJWS = prev
    return state

def verifyDEP(dep, keyStore, key):
    """
    Verifies an entire DEP. It checks if the signature of each receipt is valid,
    if the receipts are properly chained, if receipts with zero turnover are
    present as required and if the certificates used to sign the receipts are
    valid. If a key is specified it also verifies the turnover counter. Returns
    nothing on success and throws an exception otherwise.
    :param dep: The DEP as a json object.
    :param keyStore: The key store object containing the used public keys and
    certificates.
    :param key: The key used to decrypt the turnover counter as a byte list or
    None.
    :throws: NoRestoreReceiptAfterSignatureSystemFailure
    :throws: InvalidTurnoverCounterException
    :throws: CertSerialInvalidException
    :throws: CertSerialMismatchException
    :throws: NoPublicKeyException
    :throws: InvalidSignatureException
    :throws: ChainingException
    :throws: MalformedReceiptException
    :throws: UnknownAlgorithmException
    :throws: AlgorithmMismatchException
    :throws: UntrustedCertificateException
    :throws: CertificateSerialCollisionException
    :throws: SignatureSystemFailedOnInitialReceiptException
    :throws: UnsignedNullReceiptException
    :throws: NonzeroTurnoverOnInitialReceiptException
    :throws: NoCertificateGivenException
    :throws: InvalidChainingOnInitialReceiptException
    :throws: NonstandardTypeOnInitialReceiptException
    :throws: ChangingRegisterIdException
    :throws: DecreasingDateException
    :throws: ChangingSystemTypeException
    :throws: ChangingTurnoverCounterSizeException
    :throws: CertificateChainBrokenException
    :throws: DuplicateReceiptIdException
    """
    if len(dep['Belege-Gruppe']) == 1 and not dep['Belege-Gruppe'][0]['Signaturzertifikat']:
        rv = verify_receipt.ReceiptVerifier.fromKeyStore(keyStore)
        verifyGroup(dep['Belege-Gruppe'][0], rv, key)
        return

    state = VerifyGroupState()
    for group in dep['Belege-Gruppe']:
        cert = group['Signaturzertifikat']
        if not cert:
            raise NoCertificateGivenException()

        chain = group['Zertifizierungsstellen']
        verifyCert(cert, chain, keyStore)
        rv = verify_receipt.ReceiptVerifier.fromDEPCert(cert)
    
        state = verifyGroup(group, rv, key, state)

def usage():
    print("Usage: ./verify.py keyStore <key store> <dep export file> [<base64 AES key file>]")
    print("       ./verify.py json <json container file> <dep export file>")
    sys.exit(0)

if __name__ == "__main__":
    import gettext
    gettext.install('rktool', './lang', True)

    import configparser
    import json
    import sys

    import key_store

    if len(sys.argv) < 4 or len(sys.argv) > 5:
        usage()

    key = None
    keyStore = None

    if sys.argv[1] == 'keyStore':
        if len(sys.argv) == 5:
            with open(sys.argv[4]) as f:
                key = base64.b64decode(f.read().encode("utf-8"))

        config = configparser.RawConfigParser()
        config.optionxform = str
        config.read(sys.argv[2])
        keyStore = key_store.KeyStore.readStore(config)

    elif sys.argv[1] == 'json':
        if len(sys.argv) != 4:
            usage()

        with open(sys.argv[2]) as f:
            jsonStore = json.loads(f.read())

            key = utils.loadKeyFromJson(jsonStore)
            keyStore = key_store.KeyStore.readStoreFromJson(jsonStore)

    else:
        usage()

    dep = None
    with open(sys.argv[3]) as f:
        dep = json.loads(f.read())

    verifyDEP(dep, keyStore, key)

    print(_("Verification successful."))
