"""Compatibility layer for python-docx and related libraries."""
from docx.oxml.xmlchemy import BaseOxmlElement
from docx.oxml.ns import qn

def create_element(tag, **attrs):
    """Create an XML element with the given tag and attributes."""
    element = BaseOxmlElement.new(qn(tag))
    for key, value in attrs.items():
        element.set(qn(key), value)
    return element

def parse_xml(xml):
    """Create an element from an XML string."""
    return BaseOxmlElement.from_xml(xml)
