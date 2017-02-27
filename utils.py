"""
This module contains several utility functions regarding certificate and
key handling, as well has hashing, encoding and downloading receipts.
"""
from builtins import int

import base64
import datetime
import requests
import re
import uuid

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key, Encoding, PublicFormat
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature
from cryptography.x509.oid import NameOID

from six import string_types

def loadKeyFromJson(json):
    """
    Loads an AES-256 key from a cryptographic material container JSON.
    :param json: The JSON data.
    :return: The key as a byte list.
    """
    return base64.b64decode(json['base64AESKey'].encode('utf-8'))

def sha256(data):
    """
    Hashes the given data using SHA256.
    :param data: The data to be hashed as a byte list.
    :return: The hashed data as a byte list.
    """
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(data)
    return digest.finalize()

def aes256ctr(iv, key, data):
    """
    Encrypts the given data using AES-256 in CTR mode with the given IV and key.
    Can also be used for decryption due to how the CTR mode works.
    :param iv: The IV as a byte list.
    :param key: The key as a byte list.
    :param data: The data to be encrypted as a byte list.
    :return: The encrypted data as a byte list.
    """
    cipher = Cipher(algorithms.AES(key), modes.CTR(iv), backend = default_backend())
    encryptor = cipher.encryptor()
    return encryptor.update(data) + encryptor.finalize()

def loadCert(pem):
    """
    Creates a cryptography certificate object from the given PEM certificate.
    :param pem: A certificate as a PEM string.
    :return: A cryptography certificate object.
    """
    return x509.load_pem_x509_certificate(pem.encode("utf-8"), default_backend())

def loadPubKey(pem):
    """
    Creates a cryptography public key object from the given PEM public key.
    :param pem: A public key as a PEM string.
    :return: A cryptography public key object.
    """
    return load_pem_public_key(pem.encode("utf-8"), default_backend())

def loadPrivKey(pem):
    """
    Creates a cryptography private key object from the given PEM private key.
    :param pem: A private key as a PEM string.
    :return: A cryptography private key object.
    """
    return load_pem_private_key(pem.encode("utf-8"), None, default_backend())

def exportCertToPEM(cert):
    """
    Converts a cryptography certificate object to a one-line PEM string without
    header and footer (i.e. the \"-----...\" lines).
    :param cert: The certificate object.
    :return: A string containing the PEM certificate.
    """
    pem = cert.public_bytes(Encoding.PEM).decode("utf-8").splitlines()[1:-1]
    return ''.join(pem)

def exportKeyToPEM(key):
    """
    Converts a cryptography public key object to a one-line PEM string without
    header and footer (i.e. the \"-----...\" lines).
    :param key: The public key object.
    :return: A string containing the PEM public key.
    """
    pem = key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
            ).decode("utf-8").splitlines()[1:-1]
    return ''.join(pem)

def addPEMCertHeaders(cert):
    """
    Adds a certificate header and footer to a PEM certificate string.
    :param cert: The PEM certificate string.
    :return: The PEM certificate string with header and footer.
    """
    return '-----BEGIN CERTIFICATE-----\n' + '\n'.join(
            [cert[i:i+64] for i in range(0, len(cert), 64)]
            ) + '\n-----END CERTIFICATE-----'

def addPEMPubKeyHeaders(pubKey):
    """
    Adds a public key header and footer to a PEM public key string.
    :param pubKey: The PEM public key string.
    :return: The PEM public key string with header and footer.
    """
    return '-----BEGIN PUBLIC KEY-----\n' + '\n'.join(
            [pubKey[i:i+64] for i in range(0, len(pubKey), 64)]
            ) + '\n-----END PUBLIC KEY-----'

def verifyCert(cert, signCert):
    """
    Verifies that a certificate has been signed with another. Note that this
    function only verifies the cryptographic signature and is probably wrong and
    dangerous. Do not use it to verify certificates. This function only supports
    ECDSA signatures, all other signature types will fail.
    :param cert: The certificate whose signature we want to verify as a
    cryptography certificate object.
    :param signCert: The certificate that was used to sign the first certificate
    as a cryptography certificate object.
    :return: True if the signature is a valid ECDSA signature, False otherwise.
    """
    # FIXME: This is very likely wrong and we should find a better way to verify certs.
    halg = cert.signature_hash_algorithm
    sig = cert.signature
    data = cert.tbs_certificate_bytes

    pubKey = signCert.public_key()
    alg = None
    # We only support ECDSA for now
    if isinstance(pubKey, ec.EllipticCurvePublicKey):
        alg = ec.ECDSA(halg)
    else:
        return False

    ver = pubKey.verifier(sig, alg)
    ver.update(data)

    try:
        ver.verify()
        return True
    except InvalidSignature as e:
        return False

def certFingerprint(cert):
    """
    Gets a certificates SHA256 fingerprint.
    :param cert: The certificate as a cryptography certificate object.
    :return: The fingerprint as a string.
    """
    fp = cert.fingerprint(hashes.SHA256())
    if isinstance(fp, string_types):
        # Python 2
        return ':'.join('{:02x}'.format(ord(b)) for b in fp)
    else:
        # Python 3
        return ':'.join('{:02x}'.format(b) for b in fp)

def restoreb64padding(data):
    """
    Restores the padding to a base64 string without padding.
    :param data: The base64 encoded string without padding.
    :return: The base64 encoded string with padding.
    """
    needed = 4 - len(data) % 4
    if needed:
        data += '=' * needed
    return data

def getBasicCodeFromURL(url):
    """
    Downloads the basic code representation of a receipt from
    the given URL.
    :param url: The URL as a string.
    :return: The basic code representation as a string.
    """
    r = requests.get(url)
    r.raise_for_status()
    return r.json()['code']

urlHashRegex = re.compile(
        r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{11}(?![A-Za-z0-9_-])')
def getURLHashFromURL(url):
    """
    Extracts the URL hash from the given URL. If an anchor part is given,
    it is used as the hash.
    :param url: The URL to search for the hash.
    :return: The hash as a base64 URL encoded string without padding or
    None if the hash could not be found.
    """
    urlParts = url.split('#')
    if len(urlParts) >= 2:
        return urlParts[1]

    matches = urlHashRegex.findall(urlParts[0])
    if len(matches) == 0:
        return None

    return matches[-1]

def makeES256Keypair():
    """
    Generates a new EC key pair usable for JWS ES256.
    :return: The private and public key as objects.
    """
    priv = ec.generate_private_key(ec.SECP256R1(), default_backend())
    pub = priv.public_key()
    return priv, pub

def makeCertSerial():
    """
    Generates a random serial number that can be used for a certificate.
    :return: The serial as an int.
    """
    return int(uuid.uuid4())

def makeSignedCert(cpub, ccn, cvdays, cserial, spriv, scert=None):
    """
    Creates a certificate for a given public key and signs it with a given
    certificate and private key. It will reuse the subject of the signing
    certificate as the subject of the new certificate, only replacing the
    common name with the one given as parameter, if a signing certificate is
    specified, otherwise it will just use the given common name as subject
    and issuer.
    :param cpub: Public key for which to create a certificate.
    :param ccn: Common name for the new certificate.
    :param cvdays: Number of days the new certificate is valid.
    :param cserial: The serial number for the new certificate as an int.
    :param spriv: Private key for the signing certificate.
    :param scert: Certificate used to sign the new certificate, or None if
    no certificate is used.
    :return: The new certificate as an object.
    """
    if scert:
        sname = x509.Name(
            [ p for p in scert.subject if p.oid != NameOID.COMMON_NAME ]
            + [ x509.NameAttribute(NameOID.COMMON_NAME, ccn) ])
        iname = scert.subject
    else:
        sname = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ccn)])
        iname = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ccn)])

    builder = x509.CertificateBuilder()
    builder = builder.subject_name(sname)
    builder = builder.issuer_name(iname)
    builder = builder.not_valid_before(datetime.datetime.today())
    builder = builder.not_valid_after(datetime.datetime.today() +
            datetime.timedelta(cvdays, 0, 0))
    builder = builder.serial_number(cserial)
    builder = builder.public_key(cpub)
    builder = builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True
    )
    return builder.sign(private_key=spriv, algorithm=hashes.SHA256(),
            backend=default_backend())

receiptFloatRegex = re.compile(r'^-?\d+\,\d\d$')
def getReceiptFloat(fstr):
    if receiptFloatRegex.match(fstr) is None:
        return None

    try:
        return float(fstr.replace(',', '.'))
    except:
        return None
