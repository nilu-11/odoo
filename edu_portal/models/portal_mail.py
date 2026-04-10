"""Helper module for building portal welcome email HTML bodies."""
from markupsafe import Markup


def build_welcome_body(user, temp_password, role='user'):
    """Return an HTML body (Markup) for the portal welcome email."""
    name = user.name or ''
    login = user.login or ''
    role_label = (role or 'portal').capitalize()
    html = f"""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 24px; border-radius: 12px 12px 0 0;">
        <h1 style="margin: 0; font-size: 22px;">Welcome to EMIS Portal</h1>
    </div>
    <div style="background: white; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
        <p>Hello {name},</p>
        <p>Your EMIS portal account has been created. You can use it to access your <strong>{role_label}</strong> information.</p>
        <div style="background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 16px 0;">
            <p style="margin: 0 0 8px 0;"><strong>Login:</strong> {login}</p>
            <p style="margin: 0;"><strong>Temporary Password:</strong> <code>{temp_password}</code></p>
        </div>
        <p>Please log in to the portal and change your password on first login.</p>
        <p style="color: #64748b; font-size: 12px; margin-top: 24px;">If you did not expect this email, please contact your school administrator.</p>
    </div>
</div>
"""
    return Markup(html)
