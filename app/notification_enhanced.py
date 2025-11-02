from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List
from datetime import datetime, timedelta
from .models import User, Internship, UserPreferences, SentNotification
from .config import settings

class EnhancedNotificationEngine:
    def __init__(self):
        if settings.SENDGRID_API_KEY:
            self.sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        else:
            self.sg = None
        self.from_email = settings.FROM_EMAIL
    
    def process_immediate_notifications(self, db: Session, new_internships: List[Internship], 
                                       updated_internships: List[Internship]):
        """Send immediate notifications for users with immediate preference"""
        users = db.query(User).join(UserPreferences).filter(
            User.is_active == True,
            UserPreferences.notification_frequency == "immediate"
        ).all()
        
        for user in users:
            # Match new internships
            matching_new = [i for i in new_internships if self.matches_preferences(user.preferences, i) and not self.check_already_notified(db, user.id, i.id, "immediate")]
            matching_updated = [i for i in updated_internships if self.matches_preferences(user.preferences, i) and not self.check_already_notified(db, user.id, i.id, "immediate")]
            
            if matching_new or matching_updated:
                self.send_immediate_email(db, user, matching_new, matching_updated)
    
    def process_daily_digests(self, db: Session):
        """Send daily digest emails"""
        current_time = datetime.utcnow().strftime("%H:%M")
        
        # Get users who want daily digests at this time
        users = db.query(User).join(UserPreferences).filter(
            User.is_active == True,
            UserPreferences.notification_frequency == "daily",
            UserPreferences.digest_time == current_time
        ).all()
        
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        for user in users:
            # Get internships from last 24 hours that match preferences and haven't been sent in digest
            new_internships = db.query(Internship).filter(
                Internship.date_first_seen >= yesterday,
                Internship.is_active == True
            ).all()
            
            updated_internships = db.query(Internship).filter(
                Internship.date_last_updated >= yesterday,
                Internship.date_first_seen < yesterday,
                Internship.is_active == True
            ).all()
            
            # Filter by preferences and not already sent in digest
            matching_new = [i for i in new_internships 
                           if self.matches_preferences(user.preferences, i) 
                           and not self.check_already_notified(db, user.id, i.id, "daily")]
            matching_updated = [i for i in updated_internships 
                               if self.matches_preferences(user.preferences, i)
                               and not self.check_already_notified(db, user.id, i.id, "daily")]
            
            if matching_new or matching_updated:
                self.send_digest_email(db, user, matching_new, matching_updated, "daily")
    
    def process_weekly_digests(self, db: Session):
        """Send weekly digest emails"""
        current_day = datetime.utcnow().strftime("%A").lower()
        current_time = datetime.utcnow().strftime("%H:%M")
        
        users = db.query(User).join(UserPreferences).filter(
            User.is_active == True,
            UserPreferences.notification_frequency == "weekly",
            UserPreferences.digest_day == current_day,
            UserPreferences.digest_time == current_time
        ).all()
        
        last_week = datetime.utcnow() - timedelta(days=7)
        
        for user in users:
            new_internships = db.query(Internship).filter(
                Internship.date_first_seen >= last_week,
                Internship.is_active == True
            ).all()
            
            updated_internships = db.query(Internship).filter(
                Internship.date_last_updated >= last_week,
                Internship.date_first_seen < last_week,
                Internship.is_active == True
            ).all()
            
            matching_new = [i for i in new_internships 
                           if self.matches_preferences(user.preferences, i)
                           and not self.check_already_notified(db, user.id, i.id, "weekly")]
            matching_updated = [i for i in updated_internships 
                               if self.matches_preferences(user.preferences, i)
                               and not self.check_already_notified(db, user.id, i.id, "weekly")]
            
            if matching_new or matching_updated:
                self.send_digest_email(db, user, matching_new, matching_updated, "weekly")
    
    def check_already_notified(self, db: Session, user_id: int, internship_id: int, notification_type: str) -> bool:
        """Check if user was already notified about this internship with this notification type"""
        notification = db.query(SentNotification).filter(
            SentNotification.user_id == user_id,
            SentNotification.internship_id == internship_id,
            SentNotification.notification_type == notification_type
        ).first()
        
        return notification is not None
    
    def matches_preferences(self, prefs: UserPreferences, internship: Internship) -> bool:
        """Check if internship matches user preferences"""
        if not prefs:
            return False
        
        # Job type match
        job_types = prefs.job_types or []
        if job_types:
            position_lower = internship.position_title.lower()
            if not any(jt.lower() in position_lower for jt in job_types):
                return False
        
        # Sponsorship check - if user needs sponsorship, filter out "No sponsorship"
        if prefs.sponsorship_required:
            sponsorship_info = internship.sponsorship_info or ""
            sponsorship_lower = sponsorship_info.lower()
            
            # If internship explicitly says "no sponsorship", don't show it
            if "no sponsorship" in sponsorship_lower:
                return False
            
            # Note: We show "Not specified" internships even if user needs sponsorship
            # This is because "Not specified" might still offer sponsorship, we just don't know
        
        # Location match
        preferred_locations = prefs.locations or []
        if preferred_locations:
            # Handle "All Locations" - skip location filtering
            if "All Locations" in preferred_locations or "all locations" in [l.lower() for l in preferred_locations]:
                pass  # Don't filter by location
            else:
                internship_locations = internship.locations or []
                location_match = False
                
                for pref_loc in preferred_locations:
                    for int_loc in internship_locations:
                        if pref_loc.lower() in int_loc.lower() or int_loc.lower() in pref_loc.lower():
                            location_match = True
                            break
                    if location_match:
                        break
                
                # Remote matches anything
                if "remote" in [l.lower() for l in preferred_locations + (internship_locations or [])]:
                    location_match = True
                
                if not location_match:
                    return False
        
        return True
    
    def send_immediate_email(self, db: Session, user: User, new_internships: List[Internship], 
                           updated_internships: List[Internship]):
        """Send immediate notification email"""
        if not self.sg:
            print(f"SendGrid not configured. Would send immediate notification to {user.email}")
            return
            
        total = len(new_internships) + len(updated_internships)
        html = self.generate_email_html(user, new_internships, updated_internships, "immediate")
        
        try:
            message = Mail(
                from_email=self.from_email,
                to_emails=user.email,
                subject=f'🎯 {total} New Internship Alert{"s" if total > 1 else ""}!',
                html_content=html
            )
            
            response = self.sg.send(message)
            
            if response.status_code == 202:
                self.record_notifications(db, user, new_internships + updated_internships, "immediate")
                print(f"✓ Sent immediate notification to {user.email}")
                
        except Exception as e:
            print(f"Error sending email to {user.email}: {e}")
    
    def send_digest_email(self, db: Session, user: User, new_internships: List[Internship],
                         updated_internships: List[Internship], frequency: str):
        """Send digest email"""
        if not self.sg:
            print(f"SendGrid not configured. Would send {frequency} digest to {user.email}")
            return
            
        total = len(new_internships) + len(updated_internships)
        html = self.generate_email_html(user, new_internships, updated_internships, frequency)
        
        period = "Daily" if frequency == "daily" else "Weekly"
        
        try:
            message = Mail(
                from_email=self.from_email,
                to_emails=user.email,
                subject=f'📬 Your {period} Internship Digest - {total} Match{"es" if total != 1 else ""}',
                html_content=html
            )
            
            response = self.sg.send(message)
            
            if response.status_code == 202:
                self.record_notifications(db, user, new_internships + updated_internships, frequency)
                print(f"✓ Sent {frequency} digest to {user.email}")
                
        except Exception as e:
            print(f"Error sending digest to {user.email}: {e}")
    
    def generate_email_html(self, user: User, new_internships: List[Internship], 
                          updated_internships: List[Internship], notification_type: str) -> str:
        """Generate HTML email with separate sections for new and updated"""
        period = ""
        if notification_type == "daily":
            period = "in the last 24 hours"
        elif notification_type == "weekly":
            period = "this week"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 650px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                          color: white; padding: 30px 20px; border-radius: 10px 10px 0 0; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
                .section {{ padding: 20px; background: white; }}
                .section-title {{ font-size: 20px; font-weight: bold; color: #667eea; 
                                 margin: 20px 0 15px 0; padding-bottom: 10px; border-bottom: 2px solid #667eea; }}
                .internship {{ background: #f8f9fa; padding: 20px; margin: 15px 0; 
                              border-radius: 8px; border-left: 4px solid #667eea; }}
                .new-badge {{ background: #10b981; color: white; padding: 4px 12px; 
                            border-radius: 12px; font-size: 12px; font-weight: bold; display: inline-block; margin-bottom: 8px; }}
                .updated-badge {{ background: #f59e0b; color: white; padding: 4px 12px; 
                                border-radius: 12px; font-size: 12px; font-weight: bold; display: inline-block; margin-bottom: 8px; }}
                .company {{ font-size: 18px; font-weight: bold; color: #1f2937; margin-bottom: 8px; }}
                .position {{ color: #4b5563; font-size: 16px; margin: 5px 0; }}
                .details {{ font-size: 14px; color: #6b7280; margin: 10px 0; }}
                .apply-btn {{ display: inline-block; background: #667eea; color: white; 
                            padding: 12px 24px; text-decoration: none; border-radius: 6px; 
                            margin-top: 12px; font-weight: 600; }}
                .apply-btn:hover {{ background: #5568d3; }}
                .stats {{ background: #eff6ff; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                .stats-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }}
                .stat {{ text-align: center; }}
                .stat-number {{ font-size: 24px; font-weight: bold; color: #667eea; }}
                .stat-label {{ font-size: 12px; color: #6b7280; }}
                .footer {{ text-align: center; margin-top: 30px; padding: 20px; 
                          color: #9ca3af; font-size: 12px; background: #f9fafb; border-radius: 0 0 10px 10px; }}
                .footer a {{ color: #667eea; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 InternAlert</h1>
                    <p>Your personalized internship updates {period}</p>
                </div>
                
                <div class="section">
                    <div class="stats">
                        <div class="stats-grid">
                            <div class="stat">
                                <div class="stat-number">{len(new_internships)}</div>
                                <div class="stat-label">NEW POSTINGS</div>
                            </div>
                            <div class="stat">
                                <div class="stat-number">{len(updated_internships)}</div>
                                <div class="stat-label">UPDATES</div>
                            </div>
                        </div>
                    </div>
        """
        
        # New internships section
        if new_internships:
            html += '<div class="section-title">🆕 New Internships</div>'
            for internship in new_internships[:10]:  # Limit to 10
                locations = ", ".join(internship.locations) if internship.locations else "Not specified"
                html += f"""
                    <div class="internship">
                        <span class="new-badge">NEW</span>
                        <div class="company">{internship.company_name}</div>
                        <div class="position">{internship.position_title}</div>
                        <div class="details">
                            📍 {locations}<br>
                            ✈️ {internship.sponsorship_info}
                        </div>
                        <a href="{internship.application_url}" class="apply-btn">Apply Now →</a>
                    </div>
                """
        
        # Updated internships section
        if updated_internships:
            html += '<div class="section-title">🔄 Updated Internships</div>'
            for internship in updated_internships[:10]:
                locations = ", ".join(internship.locations) if internship.locations else "Not specified"
                html += f"""
                    <div class="internship">
                        <span class="updated-badge">UPDATED</span>
                        <div class="company">{internship.company_name}</div>
                        <div class="position">{internship.position_title}</div>
                        <div class="details">
                            📍 {locations}<br>
                            ✈️ {internship.sponsorship_info}
                        </div>
                        <a href="{internship.application_url}" class="apply-btn">Apply Now →</a>
                    </div>
                """
        
        html += f"""
                </div>
                
                <div class="footer">
                    <p>You're receiving this because you subscribed to InternAlert</p>
                    <p>
                        <a href="#">Manage Preferences</a> | 
                        <a href="#">Change Frequency</a> | 
                        <a href="#">Unsubscribe</a>
                    </p>
                    <p style="margin-top: 10px; font-size: 11px;">
                        Notification Type: {notification_type.title()} | 
                        Matched your filters: {', '.join(user.preferences.job_types or ['All'])}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def record_notifications(self, db: Session, user: User, internships: List[Internship], 
                           notification_type: str):
        """Record that notifications were sent"""
        for internship in internships:
            notification = SentNotification(
                user_id=user.id,
                internship_id=internship.id,
                notification_type=notification_type,
                sent_at=datetime.utcnow()
            )
            db.add(notification)
        db.commit()

