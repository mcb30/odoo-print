FROM unipartdigital/odoo-tester

# Add Odoo-required fonts and version of wkhtmltopdf
#
# Odoo requires a non-standard build of wkhtmltopdf for many use cases
# (including running without a local X display).
#
# Odoo's barcode generation uses reportlab, which tends to misdetect
# its platform and assume that it is running on Windows.  Add symlinks
# using the Windows font file names so that reportlab will find its
# required fonts anyway.
#
ENV H2P_BASE https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download
ENV H2P_VER 0.12.5
ENV H2P_REL 1
ENV H2P_FILE wkhtmltox-${H2P_VER}-${H2P_REL}.centos7.x86_64.rpm
ENV H2P_URI ${H2P_BASE}/${H2P_VER}/${H2P_FILE}
RUN dnf install -y texlive-times texlive-courier libpng15 compat-openssl10 \
	${H2P_URI} ; \
    dnf clean all
RUN mkdir -p /usr/share/fonts/default/Type1 ; \
    ln -s /usr/share/texlive/texmf-dist/fonts/type1/urw/times/utmr8a.pfb \
	  /usr/share/fonts/default/Type1/_er_____.pfb ; \
    ln -s /usr/share/texlive/texmf-dist/fonts/type1/urw/courier/ucrr8a.pfb \
	  /usr/share/fonts/default/Type1/com_____.pfb

# Add print module
#
ADD addons /opt/odoo-addons

# Module tests
#
CMD ["--test-enable", "-i", "print"]
