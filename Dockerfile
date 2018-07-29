FROM unipartdigital/odoo-tester

# Add print module
#
ADD addons /opt/odoo-addons

# Module tests
#
CMD ["--test-enable", "-i", "print"]
