#!/usr/bin/python3

import kivy
kivy.require('1.9.0')

import os 

from kivy.adapters.dictadapter import DictAdapter
from kivy.adapters.simplelistadapter import SimpleListAdapter
from kivy.app import App
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.listview import CompositeListItem
from kivy.uix.modalview import ModalView
from kivy.uix.popup import Popup
from kivy.uix.treeview import TreeView, TreeViewNode, TreeViewLabel

import receipt

class ErrorDialog(FloatLayout):
    exception = ObjectProperty(None)
    cancel = ObjectProperty(None)

class LoadDialog(FloatLayout):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)

class SaveDialog(FloatLayout):
    save = ObjectProperty(None)
    text_input = ObjectProperty(None)
    cancel = ObjectProperty(None)

class SingleValueDialog(FloatLayout):
    receive_value = ObjectProperty(None)
    text_input = ObjectProperty(None)
    cancel = ObjectProperty(None)

class TreeViewButton(Button, TreeViewNode):
    pass

class ViewReceiptWidget(BoxLayout):
    adapter = ObjectProperty(None)
    cancel = ObjectProperty(None)

    def __init__(self, receipt, algorithmPrefix, isValid, key, **kwargs):
        # TODO: handle isValid and key

        self._receipt = receipt
        self._algorithmPrefix = algorithmPrefix
        self.adapter = SimpleListAdapter(data=['asdf', 'qwer'],
                cls=Label)

        super(ViewReceiptWidget, self).__init__(**kwargs)

    def verify(self):
        # TODO
        pass

class VerifyReceiptWidget(BoxLayout):
    receiptInput = ObjectProperty(None)

    def dismissPopup(self):
        self._popup.dismiss()

    def loadReceipt(self):
        content = LoadDialog(load=self.loadReceiptCb,
                cancel=self.dismissPopup)
        self._popup = Popup(title="Load Receipt", content=content,
                size_hint=(0.9, 0.9))
        self._popup.open()

    def loadReceiptCb(self, path, filename):
        if not filename or len(filename) < 1:
            return

        with open(os.path.join(path, filename[0])) as f:
            self.receiptInput.text = f.read()

        self.dismissPopup()

    def viewReceipt(self):
        # TODO
        pass

import json
import utils
class VerifyDEPWidget(BoxLayout):
    # TODO: actual verification of the DEP

    treeView = ObjectProperty(None)
    aesInput = ObjectProperty(None)

    def addCert(self, btn):
        App.get_running_app().keyStore.putPEMCert(utils.addPEMCertHeaders(btn.text))
        App.get_running_app().updateKSWidget()

    def viewReceipt(self, btn):
        try:
            rec, prefix = receipt.Receipt.fromJWSString(btn.text)

            # TODO: properly pass isValid and key
            content = ViewReceiptWidget(rec, prefix, False, None,
                    cancel=self.dismissPopup)
            self._popup = ModalView(auto_dismiss=False)
            self._popup.add_widget(content)
            self._popup.open()
        except receipt.ReceiptException as e:
            content = ErrorDialog(exception=e, cancel=self.dismissPopup)
            self._popup = Popup(title="Error", content=content,
                    size_hint=(0.9, 0.9))
            self._popup.open()

    def updateDEPDisplay(self):
        tv = self.treeView

        for n in tv.iterate_all_nodes():
            tv.remove_node(n)

        groupIdx = 1
        for group in self._jsonDEP['Belege-Gruppe']:
            groupNode = tv.add_node(TreeViewLabel(text=('Gruppe %d' % groupIdx)))
            groupIdx += 1

            certNode = tv.add_node(TreeViewLabel(text='Signaturzertifikat'),
                    groupNode)
            chainNode = tv.add_node(TreeViewLabel(text='Zertifizierungsstellen'),
                    groupNode)
            receiptsNode = tv.add_node(TreeViewLabel(text='Belege-kompakt'),
                    groupNode)

            cert = group['Signaturzertifikat']
            if cert:
                tv.add_node(TreeViewButton(text=cert, on_press=self.addCert),
                        certNode)

            for cert in group['Zertifizierungsstellen']:
                tv.add_node(TreeViewButton(text=cert, on_press=self.addCert),
                        chainNode)

            for receipt in group['Belege-kompakt']:
                tv.add_node(TreeViewButton(text=receipt,
                    on_press=self.viewReceipt), receiptsNode)

    def dismissPopup(self):
        self._popup.dismiss()

    def loadDEP(self):
        content = LoadDialog(load=self.loadDEPCb,
                cancel=self.dismissPopup)
        self._popup = Popup(title="Load DEP", content=content,
                size_hint=(0.9, 0.9))
        self._popup.open()

    def loadDEPCb(self, path, filename):
        if not filename or len(filename) < 1:
            return

        with open(os.path.join(path, filename[0])) as f:
            self._jsonDEP = json.loads(f.read())

        self.updateDEPDisplay()
        self.dismissPopup()

    def loadAES(self):
        content = LoadDialog(load=self.loadAESCb,
                cancel=self.dismissPopup)
        self._popup = Popup(title="Load AES Key", content=content,
                size_hint=(0.9, 0.9))
        self._popup.open()

    def loadAESCb(self, path, filename):
        if not filename or len(filename) < 1:
            return

        with open(os.path.join(path, filename[0])) as f:
            self.aesInput.text = f.read()

        self.dismissPopup()

import configparser

class KeyStoreWidget(BoxLayout):
    pubKeyGroup = ObjectProperty(None)
    certGroup = ObjectProperty(None)
    treeView = ObjectProperty(None)

    def on_treeView(self, instance, value):
        tv = self.treeView
        self.pubKeyGroup = tv.add_node(TreeViewButton(text='Public Keys',
                on_press=self.addPubKey))
        self.certGroup = tv.add_node(TreeViewButton(text='Certificates',
                on_press=self.addCert))

        App.get_running_app().ksWidget = self

    def buildKSTree(self):
        if not self.treeView:
            return
        if not self.pubKeyGroup or not self.certGroup:
            return

        tv = self.treeView

        iterator = iter(tv.iterate_all_nodes(node=self.pubKeyGroup))
        next(iterator)
        for n in iterator:
            tv.remove_node(n)

        iterator = iter(tv.iterate_all_nodes(node=self.certGroup))
        next(iterator)
        for n in iterator:
            tv.remove_node(n)

        ks = App.get_running_app().keyStore
        for kid in ks.getKeyIds():
            if ks.getCert(kid):
                tv.add_node(TreeViewButton(text=kid, on_press=self.delKey),
                        self.certGroup)
            else:
                tv.add_node(TreeViewButton(text=kid, on_press=self.delKey),
                        self.pubKeyGroup)

    def delKey(self, btn):
        App.get_running_app().keyStore.delKey(btn.text)
        self.buildKSTree()

    def dismissPopup(self):
        self._popup.dismiss()

    def addPubKey(self, btn):
        content = LoadDialog(load=self.addPubKeyCbKey, cancel=self.dismissPopup)
        self._popup = Popup(title="Load PEM Public Key", content=content,
                size_hint=(0.9, 0.9))
        self._popup.open()

    def addCert(self, btn):
        content = LoadDialog(load=self.addCertCb, cancel=self.dismissPopup)
        self._popup = Popup(title="Load PEM Certificate", content=content,
                size_hint=(0.9, 0.9))
        self._popup.open()

    def addPubKeyCbKey(self, path, filename):
        if not filename or len(filename) < 1:
            return

        with open(os.path.join(path, filename[0])) as f:
            self._tmpPubKey = f.read()

        content = SingleValueDialog(receive_value=self.addPubKeyCbId,
                cancel=self.dismissPopup)

        self.dismissPopup()
        self._popup = Popup(title="Enter Public Key ID", content=content,
                size_hint=(0.9, 0.9))
        self._popup.open()

    def addPubKeyCbId(self, keyId):
        App.get_running_app().keyStore.putPEMKey(keyId, self._tmpPubKey)
        self.dismissPopup()
        self.buildKSTree()

    def addCertCb(self, path, filename):
        if not filename or len(filename) < 1:
            return

        with open(os.path.join(path, filename[0])) as f:
            App.get_running_app().keyStore.putPEMCert(f.read())

        self.dismissPopup()
        self.buildKSTree()

    def importKeyStore(self):
        content = LoadDialog(load=self.importKeyStoreCb,
                cancel=self.dismissPopup)
        self._popup = Popup(title="Load Key Store", content=content,
                size_hint=(0.9, 0.9))
        self._popup.open()

    def exportKeyStore(self):
        content = SaveDialog(save=self.exportKeyStoreCb,
                cancel=self.dismissPopup)
        self._popup = Popup(title="Save Key Store", content=content,
                size_hint=(0.9, 0.9))
        self._popup.open()

    def importKeyStoreCb(self, path, filename):
        if not filename or len(filename) < 1:
            return

        config = configparser.RawConfigParser()
        config.optionxform = str
        config.read(os.path.join(path, filename[0]))
        App.get_running_app().keyStore = key_store.KeyStore.readStore(config)

        self.dismissPopup()
        self.buildKSTree()

    def exportKeyStoreCb(self, path, filename):
        if not filename:
            return

        config = configparser.RawConfigParser()
        config.optionxform = str
        App.get_running_app().keyStore.writeStore(config)
        with open(os.path.join(path, filename), 'w') as f:
            config.write(f)

        self.dismissPopup()

class MainWidget(BoxLayout):
    pass

import key_store

class RKToolApp(App):
    keyStore = key_store.KeyStore()
    ksWidget = None

    def updateKSWidget(self):
        if self.ksWidget:
            self.ksWidget.buildKSTree()

    def build(self):
        return MainWidget()

if __name__ == '__main__':
    RKToolApp().run()
