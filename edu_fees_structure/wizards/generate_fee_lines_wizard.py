from odoo import api, fields, models
from odoo.exceptions import UserError


class GenerateFeeLinesWizard(models.TransientModel):
    _name = 'edu.fee.structure.generate.wizard'
    _description = 'Generate Fee Structure Lines Wizard'

    fee_structure_id = fields.Many2one(
        comodel_name='edu.fee.structure',
        string='Fee Structure',
        required=True,
        readonly=True,
    )
    program_id = fields.Many2one(
        related='fee_structure_id.program_id',
        string='Program',
    )
    company_id = fields.Many2one(
        related='fee_structure_id.company_id',
        string='Company',
    )
    fee_head_ids = fields.Many2many(
        comodel_name='edu.fee.head',
        string='Fee Heads',
        required=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        help='Select the fee heads to generate lines for. '
             'Admission / one-time fee heads will only be added to the first progression stage.',
    )

    def action_generate(self):
        self.ensure_one()
        structure = self.fee_structure_id

        if structure.state == 'closed':
            raise UserError('Cannot modify a closed fee structure.')
        if not structure.program_id:
            raise UserError('Select a program before generating fee lines.')

        program_terms = self.env['edu.program.term'].search(
            [('program_id', '=', structure.program_id.id)],
            order='progression_no',
        )
        if not program_terms:
            raise UserError(
                f'No program terms found for "{structure.program_id.name}". '
                'Generate them from the Program form first.'
            )

        # Build set of existing (program_term, fee_head) pairs to skip duplicates
        existing_pairs = {
            (line.program_term_id.id, line.fee_head_id.id)
            for line in structure.line_ids
        }

        # Separate admission / one-time heads from recurring heads
        admission_heads = self.fee_head_ids.filtered(
            lambda h: h.fee_type == 'admission' or h.is_one_time
        )
        recurring_heads = self.fee_head_ids - admission_heads

        first_term = program_terms[0] if program_terms else False
        vals_list = []

        # Admission / one-time heads: only first progression, sequenced first
        if first_term and admission_heads:
            for seq, head in enumerate(admission_heads.sorted('name'), start=1):
                pair = (first_term.id, head.id)
                if pair not in existing_pairs:
                    vals_list.append({
                        'fee_structure_id': structure.id,
                        'program_term_id': first_term.id,
                        'fee_head_id': head.id,
                        'amount': 0.0,
                        'sequence': seq,
                    })
                    existing_pairs.add(pair)

        # Recurring heads: every program term
        for pt in program_terms:
            for seq_offset, head in enumerate(recurring_heads.sorted('name'), start=10):
                pair = (pt.id, head.id)
                if pair not in existing_pairs:
                    vals_list.append({
                        'fee_structure_id': structure.id,
                        'program_term_id': pt.id,
                        'fee_head_id': head.id,
                        'amount': 0.0,
                        'sequence': seq_offset,
                    })
                    existing_pairs.add(pair)

        if not vals_list:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Nothing to Generate',
                    'message': 'Fee lines for all selected heads already exist.',
                    'type': 'info',
                    'sticky': False,
                },
            }

        self.env['edu.fee.structure.line'].create(vals_list)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Fee Lines Generated',
                'message': f'Created {len(vals_list)} fee line(s) for "{structure.name}".',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
