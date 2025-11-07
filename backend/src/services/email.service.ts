/**
 * Email Service
 * Handles sending emails for authentication, verification, and notifications
 * Production-ready with error handling, logging, and retry logic
 */

import nodemailer from 'nodemailer';
import { securityConfig } from '../config/auth.config';

/**
 * Email templates for different types of emails
 */
interface EmailTemplate {
  subject: string;
  html: string;
  text: string;
}

/**
 * Email service configuration
 */
interface EmailConfig {
  host: string;
  port: number;
  secure: boolean;
  auth: {
    user: string;
    pass: string;
  };
  from: string;
}

/**
 * Email Service Class
 * Handles all email operations with proper error handling and logging
 */
export class EmailService {
  private transporter: nodemailer.Transporter | null = null;
  private readonly config: EmailConfig;

  constructor() {
    this.config = {
      host: process.env.SMTP_HOST || '',
      port: parseInt(process.env.SMTP_PORT || '587'),
      secure: process.env.SMTP_SECURE === 'true',
      auth: {
        user: process.env.SMTP_USER || '',
        pass: process.env.SMTP_PASSWORD || '',
      },
      from: process.env.EMAIL_FROM || 'noreply@lingumentor.com',
    };

    this.initializeTransporter();
  }

  /**
   * Initialize the email transporter with configuration
   */
  private initializeTransporter(): void {
    try {
      // Only create transporter if email configuration is provided
      if (this.config.host && this.config.auth.user && this.config.auth.pass) {
        this.transporter = nodemailer.createTransport({
          host: this.config.host,
          port: this.config.port,
          secure: this.config.secure,
          auth: {
            user: this.config.auth.user,
            pass: this.config.auth.pass,
          },
          // Production settings
          pool: true, // Use pooled connections
          maxConnections: 5,
          maxMessages: 100,
          rateDelta: 20000, // 20 seconds
          rateLimit: 5, // Max 5 messages per 20 seconds
        });

        console.log('✅ Email service initialized successfully');
      } else {
        console.log('⚠️ Email service not configured - emails will be logged to console');
      }
    } catch (error) {
      console.error('❌ Failed to initialize email transporter:', error);
      this.transporter = null;
    }
  }

  /**
   * Verify email configuration and connection
   */
  async verifyConnection(): Promise<boolean> {
    if (!this.transporter) {
      console.log('Email service not configured');
      return false;
    }

    try {
      await this.transporter.verify();
      console.log('✅ Email transporter verified');
      return true;
    } catch (error) {
      console.error('❌ Email transporter verification failed:', error);
      return false;
    }
  }

  /**
   * Send email with retry logic and error handling
   */
  private async sendEmailWithRetry(
    to: string,
    template: EmailTemplate,
    retryCount = 0
  ): Promise<void> {
    const maxRetries = 3;
    
    try {
      if (!this.transporter) {
        // In development, log emails to console
        console.log('\n📧 EMAIL (Development Mode)');
        console.log(`To: ${to}`);
        console.log(`Subject: ${template.subject}`);
        console.log(`HTML: ${template.html}`);
        console.log(`Text: ${template.text}\n`);
        return;
      }

      const mailOptions = {
        from: this.config.from,
        to,
        subject: template.subject,
        html: template.html,
        text: template.text,
      };

      const result = await this.transporter.sendMail(mailOptions);
      console.log(`✅ Email sent successfully to ${to}:`, result.messageId);
      
    } catch (error) {
      console.error(`❌ Failed to send email to ${to} (attempt ${retryCount + 1}):`, error);
      
      if (retryCount < maxRetries) {
        const delay = Math.pow(2, retryCount) * 1000; // Exponential backoff
        console.log(`🔄 Retrying in ${delay}ms...`);
        await new Promise(resolve => setTimeout(resolve, delay));
        return this.sendEmailWithRetry(to, template, retryCount + 1);
      }
      
      throw error; // Re-throw after max retries
    }
  }

  /**
   * Generate email verification template
   */
  private generateVerificationEmail(token: string, userName: string): EmailTemplate {
    const verificationUrl = `${process.env.FRONTEND_URL || 'http://localhost:3000'}/verify-email?token=${token}`;
    
    return {
      subject: 'Verify Your LinguaMentor Account',
      html: `
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>Verify Your Account</title>
          <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background-color: #4F46E5; color: white; padding: 20px; text-align: center; }
            .content { background-color: #f9f9f9; padding: 30px; border-radius: 5px; }
            .button { display: inline-block; padding: 12px 24px; background-color: #4F46E5; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
            .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #666; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1>LinguaMentor</h1>
            </div>
            <div class="content">
              <h2>Welcome to LinguaMentor, ${userName}!</h2>
              <p>Thank you for signing up. To complete your registration and start your language learning journey, please verify your email address by clicking the button below:</p>
              <div style="text-align: center;">
                <a href="${verificationUrl}" class="button">Verify Email Address</a>
              </div>
              <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
              <p><a href="${verificationUrl}">${verificationUrl}</a></p>
              <p>This verification link will expire in 24 hours for security reasons.</p>
              <p>If you didn't create this account, please ignore this email.</p>
            </div>
            <div class="footer">
              <p>This is an automated message from LinguaMentor. Please do not reply to this email.</p>
            </div>
          </div>
        </body>
        </html>
      `,
      text: `
Welcome to LinguaMentor, ${userName}!

Thank you for signing up. To complete your registration, please verify your email address by visiting:
${verificationUrl}

This verification link will expire in 24 hours for security reasons.

If you didn't create this account, please ignore this email.

This is an automated message from LinguaMentor.
      `
    };
  }

  /**
   * Generate password reset email template
   */
  private generatePasswordResetEmail(token: string, userName: string): EmailTemplate {
    const resetUrl = `${process.env.FRONTEND_URL || 'http://localhost:3000'}/reset-password?token=${token}`;
    
    return {
      subject: 'Reset Your LinguaMentor Password',
      html: `
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>Reset Your Password</title>
          <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background-color: #DC2626; color: white; padding: 20px; text-align: center; }
            .content { background-color: #f9f9f9; padding: 30px; border-radius: 5px; }
            .button { display: inline-block; padding: 12px 24px; background-color: #DC2626; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
            .footer { text-align: center; margin-top: 30px; font-size: 12px; color: #666; }
            .warning { background-color: #fef3c7; border: 1px solid #f59e0b; padding: 15px; border-radius: 5px; margin: 20px 0; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1>LinguaMentor</h1>
            </div>
            <div class="content">
              <h2>Password Reset Request</h2>
              <p>Hello ${userName},</p>
              <p>We received a request to reset your LinguaMentor account password. Click the button below to create a new password:</p>
              <div style="text-align: center;">
                <a href="${resetUrl}" class="button">Reset Password</a>
              </div>
              <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
              <p><a href="${resetUrl}">${resetUrl}</a></p>
              <div class="warning">
                <strong>⚠️ Security Notice:</strong> This password reset link will expire in 1 hour for your security. If you didn't request this password reset, please ignore this email and your password will remain unchanged.
              </div>
            </div>
            <div class="footer">
              <p>This is an automated message from LinguaMentor. Please do not reply to this email.</p>
            </div>
          </div>
        </body>
        </html>
      `,
      text: `
Hello ${userName},

We received a request to reset your LinguaMentor account password. Please visit:
${resetUrl}

⚠️ Security Notice: This password reset link will expire in 1 hour for your security. If you didn't request this password reset, please ignore this email and your password will remain unchanged.

This is an automated message from LinguaMentor.
      `
    };
  }

  /**
   * Send email verification email
   */
  async sendVerificationEmail(email: string, token: string, userName: string): Promise<void> {
    try {
      const template = this.generateVerificationEmail(token, userName);
      await this.sendEmailWithRetry(email, template);
    } catch (error) {
      console.error('Failed to send verification email:', error);
      throw new Error('Failed to send verification email');
    }
  }

  /**
   * Send password reset email
   */
  async sendPasswordResetEmail(email: string, token: string, userName: string): Promise<void> {
    try {
      const template = this.generatePasswordResetEmail(token, userName);
      await this.sendEmailWithRetry(email, template);
    } catch (error) {
      console.error('Failed to send password reset email:', error);
      throw new Error('Failed to send password reset email');
    }
  }
}

/**
 * Singleton instance of email service
 */
export const emailService = new EmailService();

export default emailService;