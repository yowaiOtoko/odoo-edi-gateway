{
    'name': 'EDI Gateway',
    'version': '19.0.1.0.1',
    'category': 'Accounting/EDI',
    'summary': 'French e-invoicing EDI gateway — send, receive, lifecycle tracking via PDP',
    'author': 'invo facturation',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'queue_job',
    ],
    'external_dependencies': {
        'python': ['factur-x', 'requests', 'cryptography'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/res_company_views.xml',
        'views/account_move_views.xml',
        'views/edi_inbound_invoice_views.xml',
        'views/edi_invoice_log_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
