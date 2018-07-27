FROM unipartdigital/odoo-tester

# Add Odoo-required version of wkhtmltopdf
#
# Odoo requires a non-standard build of wkhtmltopdf for many use cases
# (including running without a local X display).
#
ENV H2P_BASE https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download
ENV H2P_VER 0.12.5
ENV H2P_REL 1
ENV H2P_FILE wkhtmltox-${H2P_VER}-${H2P_REL}.centos7.x86_64.rpm
ENV H2P_URI ${H2P_BASE}/${H2P_VER}/${H2P_FILE}
RUN dnf install -y libpng15 compat-openssl10 ${H2P_URI} ; \
    dnf clean all

# Add print module
#
ADD addons /opt/odoo-addons

# Module tests
#
CMD ["--test-enable", "-i", "print"]
