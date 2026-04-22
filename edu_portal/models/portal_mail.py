from markupsafe import Markup


class PortalMail:
    """Helper class for building portal welcome emails."""

    @staticmethod
    def build_welcome_email(user, password, role):
        """Build HTML body for the portal welcome email.

        :param user: res.users record
        :param password: str — temporary password
        :param role: str — 'student', 'parent', or 'teacher'
        :returns: Markup (safe HTML string)
        """
        role_labels = {
            'student': 'Student',
            'parent': 'Parent',
            'teacher': 'Teacher',
        }
        role_label = role_labels.get(role, role.title())

        html = """
<div style="font-family: Arial, Helvetica, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%);
                color: #fff; padding: 30px; border-radius: 12px 12px 0 0;
                text-align: center;">
        <h1 style="margin: 0; font-size: 24px;">Welcome to the Education Portal</h1>
        <p style="margin: 10px 0 0; opacity: 0.9;">%(role_label)s Access</p>
    </div>

    <div style="background: #fff; padding: 30px; border: 1px solid #e0e0e0;
                border-top: none; border-radius: 0 0 12px 12px;">
        <p>Dear <strong>%(user_name)s</strong>,</p>

        <p>Your %(role_label)s portal account has been created. You can now
           access the Education Portal to view your information and stay
           connected with the institution.</p>

        <div style="background: #f8f9fa; border-radius: 8px; padding: 20px;
                    margin: 20px 0; border-left: 4px solid #667eea;">
            <p style="margin: 0 0 10px; font-weight: bold; color: #333;">
                Your Login Credentials
            </p>
            <table style="width: 100%%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 5px 0; color: #666; width: 120px;">Login:</td>
                    <td style="padding: 5px 0; font-weight: bold;">%(login)s</td>
                </tr>
                <tr>
                    <td style="padding: 5px 0; color: #666;">Password:</td>
                    <td style="padding: 5px 0; font-weight: bold; font-family: monospace;
                               background: #fff3cd; padding: 4px 8px; border-radius: 4px;
                               display: inline-block;">%(password)s</td>
                </tr>
            </table>
        </div>

        <div style="background: #fff3cd; border-radius: 8px; padding: 15px;
                    margin: 20px 0; border-left: 4px solid #ffc107;">
            <p style="margin: 0; color: #856404;">
                <strong>Important:</strong> Please change your password after
                your first login for security purposes.
            </p>
        </div>

        <p style="color: #666; font-size: 13px; margin-top: 30px;
                  border-top: 1px solid #eee; padding-top: 15px;">
            If you did not expect this email, please contact the institution
            administration.
        </p>
    </div>
</div>
""" % {
            'role_label': role_label,
            'user_name': user.name or '',
            'login': user.login or '',
            'password': password or '',
        }

        return Markup(html)
