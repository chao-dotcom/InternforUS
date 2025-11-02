from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from sqlalchemy.orm import Session
from typing import List
import os
from .models import User, Internship, UserPreferences, SentNotification
from .config import settings
from datetime import datetime

class NotificationEngine:
    def __init__(self):
        if settings.SENDGRID_API_KEY:
            self.sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        else:
            self.sg = None
        self.from_email = settings.FROM_EMAIL
    
    def match_internships_to_users(self, db: Session, new_internships: List[Internship]):
        """Find users who should be notified about each internship"""
        matches = []
        
        for internship in new_internships:
            matching_users = self.find_matching_users(db, internship)
            if matching_users:
                matches.append((internship, matching_users))
        
        return matches
    
    def find_matching_users(self, db: Session, internship: Internship) -> List[User]:
        """Find users with preferences matching this internship"""
        matching_users = []
        
        # Get all active users with preferences
        users = db.query(User).filter(
            User.is_active == True
        ).join(UserPreferences).all()
        
        for user in users:
            if self.check_already_notified(db, user.id, internship.id):
                continue
            
            if self.matches_preferences(user.preferences, internship):
                matching_users.append(user)
        
        return matching_users
    
    def check_already_notified(self, db: Session, user_id: int, internship_id: int) -> bool:
        """Check if user was already notified about this internship"""
        notification = db.query(SentNotification).filter(
            SentNotification.user_id == user_id,
            SentNotification.internship_id == internship_id
        ).first()
        
        return notification is not None
    
    def matches_preferences(self, prefs: UserPreferences, internship: Internship) -> bool:
        """Check if internship matches user preferences"""
        if not prefs:
            return False
        
        # Check job type match
        job_types = prefs.job_types or []
        if job_types:
            position_lower = internship.position_title.lower()
            if not any(jt.lower() in position_lower for jt in job_types):
                return False
        
        # Check sponsorship requirements
        if prefs.sponsorship_required:
            if "no sponsorship" in internship.sponsorship_info.lower():
                return False
        
        # Check location preferences
        preferred_locations = prefs.locations or []
        if preferred_locations:
            internship_locations = internship.locations or []
            location_match = False
            
            for pref_loc in preferred_locations:
                for int_loc in internship_locations:
                    if pref_loc.lower() in int_loc.lower() or int_loc.lower() in pref_loc.lower():
                        location_match = True
                        break
                if location_match:
                    break
            
            # Allow if Remote is in preferences or internship
            if "remote" in [l.lower() for l in preferred_locations + internship_locations]:
                location_match = True
            
            if not location_match:
                return False
        
        return True
    
    def generate_email_html(self, user: User, internships: List[Internship]) -> str:
        """Generate HTML email content"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #4F46E5; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .internship {{ background: #f9fafb; padding: 15px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #4F46E5; }}
                .company {{ font-size: 18px; font-weight: bold; color: #1f2937; }}
                .position {{ color: #4b5563; margin: 5px 0; }}
                .details {{ font-size: 14px; color: #6b7280; }}
                .apply-btn {{ display: inline-block; background: #4F46E5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 10px; }}
                .footer {{ text-align: center; margin-top: 30px; color: #9ca3af; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 New Internship Alerts</h1>
                    <p>We found {len(internships)} new internship(s) matching your preferences!</p>
                </div>
                
                <div style="padding: 20px;">
        """
        
        for internship in internships:
            locations = ", ".join(internship.locations) if internship.locations else "Not specified"
            html += f"""
                    <div class="internship">
                        <div class="company">{internship.company_name}</div>
                        <div class="position">{internship.position_title}</div>
                        <div class="details">
                            📍 {locations}<br>
                            ✈️ {internship.sponsorship_info}
                        </div>
                        <a href="{internship.application_url}" class="apply-btn">Apply Now</a>
                    </div>
            """
        
        html += f"""
                </div>
                
                <div class="footer">
                    <p>You're receiving this because you subscribed to InternAlert</p>
                    <p><a href="#">Manage Preferences</a> | <a href="#">Unsubscribe</a></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_notification(self, user: User, internships: List[Internship]) -> bool:
        """Send email notification to user"""
        if not self.sg:
            print(f"SendGrid not configured. Would send email to {user.email} for {len(internships)} internships")
            return False
            
        try:
            html_content = self.generate_email_html(user, internships)
            
            message = Mail(
                from_email=self.from_email,
                to_emails=user.email,
                subject=f'🎯 {len(internships)} New Internship{"s" if len(internships) > 1 else ""} Match Your Profile!',
                html_content=html_content
            )
            
            response = self.sg.send(message)
            print(f"Email sent to {user.email} - Status: {response.status_code}")
            return response.status_code == 202
            
        except Exception as e:
            print(f"Error sending email to {user.email}: {e}")
            return False
    
    def record_notification(self, db: Session, user_id: int, internship_id: int):
        """Record that notification was sent"""
        notification = SentNotification(
            user_id=user_id,
            internship_id=internship_id,
            sent_at=datetime.utcnow()
        )
        db.add(notification)
        db.commit()
    
    def process_notifications(self, db: Session, new_internships: List[Internship]):
        """Main function to process and send all notifications"""
        matches = self.match_internships_to_users(db, new_internships)
        
        print(f"Found {len(matches)} internship-user matches")
        
        # Group internships by user for batch sending
        user_internships = {}
        for internship, users in matches:
            for user in users:
                if user.id not in user_internships:
                    user_internships[user.id] = {'user': user, 'internships': []}
                user_internships[user.id]['internships'].append(internship)
        
        # Send emails
        for user_data in user_internships.values():
            user = user_data['user']
            internships = user_data['internships']
            
            success = self.send_notification(user, internships)
            
            if success:
                for internship in internships:
                    self.record_notification(db, user.id, internship.id)
        
        print(f"Sent {len(user_internships)} notification emails")

