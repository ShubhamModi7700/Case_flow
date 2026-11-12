from email.message import EmailMessage

from app.services.document_extraction import extract_eml


def test_html_only_email_is_searchable_and_ignores_scripts():
    message = EmailMessage()
    message['Subject'] = 'Delivery'
    message.set_content('<html><body><p>Delivery agreed for 30 April.</p><script>secret code</script></body></html>', subtype='html')
    extracted = extract_eml(message.as_bytes())
    assert 'Delivery agreed for 30 April.' in extracted.sections[0].text
    assert 'secret code' not in extracted.sections[0].text


def test_plain_text_preferred_over_html_alternative():
    message = EmailMessage()
    message.set_content('Original plain text')
    message.add_alternative('<p>HTML duplicate</p>', subtype='html')
    extracted = extract_eml(message.as_bytes())
    assert 'Original plain text' in extracted.sections[0].text
    assert 'HTML duplicate' not in extracted.sections[0].text
