"""
Google Classroom API Service Module.

Provides authentication and API interactions with Google Classroom.
"""

import os
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import io
from googleapiclient.http import MediaIoBaseDownload

from config.settings import settings


class GoogleClassroomService:
    """
    Google Classroom API service for authentication and API calls.
    
    Features:
    - OAuth2 authentication with token caching
    - Course management (read)
    - CourseWork (assignments) fetching
    - Student submissions fetching and grading
    - Rubric management
    """
    
    def __init__(self):
        """Initialize Google Classroom service."""
        self.credentials = None
        self.service = None
        self.drive_service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize the Google Classroom API service with authentication."""
        if not settings.enable_google_classroom:
            print("ℹ️  Google Classroom integration is disabled")
            return
        
        if not settings.google_classroom_credentials_file:
            print("⚠️  Google Classroom credentials file not configured")
            return
        
        creds = None
        token_file = settings.google_classroom_token_file
        
        # Sort scopes to ensure consistent ordering (prevents scope mismatch errors)
        sorted_scopes = sorted(settings.google_classroom_scopes)
        
        # Load existing token if available
        if os.path.exists(token_file):
            try:
                creds = Credentials.from_authorized_user_file(
                    token_file,
                    sorted_scopes
                )
            except Exception as e:
                error_msg = str(e).lower()
                # Handle scope mismatch errors by deleting the token and re-authenticating
                if 'scope' in error_msg or 'scopes' in error_msg:
                    print(f"⚠️  OAuth scope mismatch detected: {e}")
                    print(f"🔄 Deleting token file and re-authenticating...")
                    try:
                        os.remove(token_file)
                        print(f"✅ Deleted {token_file}")
                    except Exception as delete_error:
                        print(f"⚠️  Could not delete token file: {delete_error}")
                    creds = None
                else:
                    print(f"⚠️  Error loading token: {e}")
                    creds = None
        
        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    print("🔄 Refreshing expired token...")
                    creds.refresh(Request())
                    print("✅ Token refreshed successfully")
                except Exception as e:
                    print(f"⚠️  Error refreshing token: {e}")
                    print("🔄 Will request new authentication...")
                    creds = None
            
            if not creds:
                if not os.path.exists(settings.google_classroom_credentials_file):
                    raise FileNotFoundError(
                        f"Credentials file not found: {settings.google_classroom_credentials_file}"
                    )
                
                print("🔐 Starting OAuth authentication flow...")
                print(f"📋 Requesting {len(sorted_scopes)} OAuth scopes...")
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        settings.google_classroom_credentials_file,
                        sorted_scopes
                    )
                    # prompt='consent' forces re-consent to update scopes
                    creds = flow.run_local_server(port=0, prompt='consent')
                    print("✅ Authentication successful")
                except Exception as oauth_error:
                    error_msg = str(oauth_error).lower()
                    if 'scope' in error_msg or 'scopes' in error_msg:
                        print(f"\n⚠️  OAuth scope mismatch during authorization!")
                        print("💡 This happens when previously authorized scopes don't match current scopes.")
                        print("\n🔧 Solutions:")
                        print("   1. Visit: https://myaccount.google.com/permissions")
                        print("   2. Find 'Study Search Agent' and remove access")
                        print("   3. Run this script again to re-authorize with correct scopes")
                        print("\n   OR use the force re-consent flow (may work automatically)...")
                        
                        # Try one more time with force consent
                        try:
                            print("\n🔄 Attempting automatic scope update with forced re-consent...")
                            flow = InstalledAppFlow.from_client_secrets_file(
                                settings.google_classroom_credentials_file,
                                sorted_scopes
                            )
                            # Force consent screen to update scopes
                            creds = flow.run_local_server(
                                port=0,
                                authorization_prompt_message='',
                                success_message='Authentication successful! You can close this window.',
                                open_browser=True
                            )
                            print("✅ Re-authorization successful with updated scopes")
                        except Exception as retry_error:
                            print(f"❌ Automatic retry failed: {retry_error}")
                            raise oauth_error
                    else:
                        raise
            
            # Save credentials for future use
            try:
                with open(token_file, 'w') as token:
                    token.write(creds.to_json())
                print(f"💾 Saved credentials to {token_file}")
            except Exception as e:
                print(f"⚠️  Could not save token: {e}")
        
        self.credentials = creds
        
        try:
            self.service = build('classroom', 'v1', credentials=creds)
            self.drive_service = build('drive', 'v3', credentials=creds)
            print("✅ Google Classroom and Drive services initialized successfully")
        except Exception as e:
            print(f"❌ Error building Classroom service: {e}")
            raise
    
    def is_available(self) -> bool:
        """Check if Google Classroom service is available."""
        return self.service is not None
    
    def list_courses(
        self,
        teacher_id: Optional[str] = None,
        student_id: Optional[str] = None,
        page_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List courses accessible to the authenticated user.
        
        Args:
            teacher_id: Filter by teacher ID (use 'me' for current user)
            student_id: Filter by student ID
            page_size: Number of courses to return per page
            
        Returns:
            List of course dictionaries
        """
        if not self.is_available():
            return []
        
        try:
            params = {'pageSize': page_size}
            if teacher_id:
                params['teacherId'] = teacher_id
            if student_id:
                params['studentId'] = student_id
            
            results = self.service.courses().list(**params).execute()
            courses = results.get('courses', [])
            
            return courses
        except HttpError as e:
            print(f"❌ Error listing courses: {e}")
            return []
    
    def get_course(self, course_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a specific course.
        
        Args:
            course_id: The course identifier
            
        Returns:
            Course dictionary or None if not found
        """
        if not self.is_available():
            return None
        
        try:
            course = self.service.courses().get(id=course_id).execute()
            return course
        except HttpError as e:
            print(f"❌ Error getting course {course_id}: {e}")
            return None
    
    def list_course_work(
        self,
        course_id: str,
        page_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List all coursework (assignments) for a course.
        
        Args:
            course_id: The course identifier
            page_size: Number of assignments to return per page
            
        Returns:
            List of coursework dictionaries
        """
        if not self.is_available():
            return []
        
        try:
            print(f"🔍 Fetching coursework for course ID: {course_id}")
            results = self.service.courses().courseWork().list(
                courseId=course_id,
                pageSize=page_size
            ).execute()
            
            print(f"📦 Raw API response: {json.dumps(results, indent=2)}")
            
            coursework = results.get('courseWork', [])
            print(f"📚 Found {len(coursework)} coursework items")
            return coursework
        except HttpError as e:
            print(f"❌ Error listing coursework for course {course_id}: {e}")
            print(f"❌ Error details: {e.error_details if hasattr(e, 'error_details') else 'N/A'}")
            return []
    
    def list_course_work_materials(
        self,
        course_id: str,
        page_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List all coursework materials (non-graded materials) for a course.
        
        Args:
            course_id: The course identifier
            page_size: Number of materials to return per page
            
        Returns:
            List of coursework material dictionaries
        """
        if not self.is_available():
            return []
        
        try:
            print(f"🔍 Fetching coursework materials for course ID: {course_id}")
            results = self.service.courses().courseWorkMaterials().list(
                courseId=course_id,
                pageSize=page_size
            ).execute()
            
            print(f"📦 Raw materials API response: {json.dumps(results, indent=2)}")
            
            materials = results.get('courseWorkMaterial', [])
            print(f"📚 Found {len(materials)} material items")
            return materials
        except HttpError as e:
            print(f"❌ Error listing materials for course {course_id}: {e}")
            print(f"❌ Error details: {e.error_details if hasattr(e, 'error_details') else 'N/A'}")
            return []
    
    def get_course_work(
        self,
        course_id: str,
        coursework_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get details of a specific coursework assignment.
        
        Args:
            course_id: The course identifier
            coursework_id: The coursework identifier
            
        Returns:
            Coursework dictionary or None if not found
        """
        if not self.is_available():
            return None
        
        try:
            coursework = self.service.courses().courseWork().get(
                courseId=course_id,
                id=coursework_id
            ).execute()
            return coursework
        except HttpError as e:
            print(f"❌ Error getting coursework {coursework_id}: {e}")
            return None
    
    def list_student_submissions(
        self,
        course_id: str,
        coursework_id: str,
        page_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List all student submissions for a coursework assignment.
        
        Args:
            course_id: The course identifier
            coursework_id: The coursework identifier
            page_size: Number of submissions to return per page
            
        Returns:
            List of submission dictionaries
        """
        if not self.is_available():
            return []
        
        try:
            results = self.service.courses().courseWork().studentSubmissions().list(
                courseId=course_id,
                courseWorkId=coursework_id,
                pageSize=page_size
            ).execute()
            
            submissions = results.get('studentSubmissions', [])
            return submissions
        except HttpError as e:
            print(f"❌ Error listing submissions: {e}")
            return []
    
    def get_student_submission(
        self,
        course_id: str,
        coursework_id: str,
        submission_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific student submission.
        
        Args:
            course_id: The course identifier
            coursework_id: The coursework identifier
            submission_id: The submission identifier
            
        Returns:
            Submission dictionary or None if not found
        """
        if not self.is_available():
            return None
        
        try:
            submission = self.service.courses().courseWork().studentSubmissions().get(
                courseId=course_id,
                courseWorkId=coursework_id,
                id=submission_id
            ).execute()
            return submission
        except HttpError as e:
            print(f"❌ Error getting submission {submission_id}: {e}")
            return None
    
    def grade_submission(
        self,
        course_id: str,
        coursework_id: str,
        submission_id: str,
        grade: float,
        feedback: Optional[str] = None
    ) -> bool:
        """
        Grade a student submission.
        
        Args:
            course_id: The course identifier
            coursework_id: The coursework identifier
            submission_id: The submission identifier
            grade: The grade to assign (0-100 or as per max points)
            feedback: Optional feedback text
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            # Prepare the grade update
            body = {
                'assignedGrade': grade
            }
            
            # Add draft feedback if provided
            if feedback:
                body['draftGrade'] = grade
            
            # Update the submission
            updated_submission = self.service.courses().courseWork().studentSubmissions().patch(
                courseId=course_id,
                courseWorkId=coursework_id,
                id=submission_id,
                updateMask='assignedGrade,draftGrade',
                body=body
            ).execute()
            
            # Return the submission (mark it as graded)
            self.service.courses().courseWork().studentSubmissions().return_(
                courseId=course_id,
                courseWorkId=coursework_id,
                id=submission_id
            ).execute()
            
            print(f"✅ Successfully graded submission {submission_id}")
            return True
            
        except HttpError as e:
            print(f"❌ Error grading submission: {e}")
            return False
    
    def list_students(self, course_id: str, page_size: int = 100) -> List[Dict[str, Any]]:
        """
        List all students enrolled in a course.
        
        Args:
            course_id: The course identifier
            page_size: Number of students to return per page
            
        Returns:
            List of student dictionaries
        """
        if not self.is_available():
            return []
        
        try:
            results = self.service.courses().students().list(
                courseId=course_id,
                pageSize=page_size
            ).execute()
            
            students = results.get('students', [])
            return students
        except HttpError as e:
            print(f"❌ Error listing students: {e}")
            return []
    
    def get_rubric(
        self,
        course_id: str,
        coursework_id: str,
        rubric_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a rubric for a coursework assignment.
        
        Args:
            course_id: The course identifier
            coursework_id: The coursework identifier
            rubric_id: The rubric identifier
            
        Returns:
            Rubric dictionary or None if not found
        """
        if not self.is_available():
            return None
        
        try:
            rubric = self.service.courses().courseWork().rubrics().get(
                courseId=course_id,
                courseWorkId=coursework_id,
                id=rubric_id
            ).execute()
            return rubric
        except HttpError as e:
            print(f"❌ Error getting rubric: {e}")
            return None
    
    def list_rubrics(
        self,
        course_id: str,
        coursework_id: str
    ) -> List[Dict[str, Any]]:
        """
        List all rubrics for a coursework assignment.
        
        Args:
            course_id: The course identifier
            coursework_id: The coursework identifier
            
        Returns:
            List of rubric dictionaries
        """
        if not self.is_available():
            return []
        
        try:
            results = self.service.courses().courseWork().rubrics().list(
                courseId=course_id,
                courseWorkId=coursework_id
            ).execute()
            
            rubrics = results.get('rubrics', [])
            return rubrics
        except HttpError as e:
            print(f"❌ Error listing rubrics: {e}")
            return []
    
    def get_drive_document_content(self, file_id: str) -> Optional[str]:
        """
        Fetch the content of a Google Drive document (Google Docs).
        
        Args:
            file_id: The Google Drive file ID
            
        Returns:
            Document content as text, or None if error
        """
        if not self.is_available() or not self.drive_service:
            return None
        
        try:
            print(f"📄 Fetching Google Drive document content for file ID: {file_id}")
            
            # Export the Google Doc as plain text
            request = self.drive_service.files().export_media(
                fileId=file_id,
                mimeType='text/plain'
            )
            
            # Download the content
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            done = False
            
            while done is False:
                status, done = downloader.next_chunk()
            
            # Get the text content
            content = file_content.getvalue().decode('utf-8')
            print(f"✅ Successfully fetched document content ({len(content)} characters)")
            return content
            
        except HttpError as e:
            print(f"❌ Error fetching Drive document {file_id}: {e}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error fetching Drive document {file_id}: {e}")
            return None


# Global service instance
_classroom_service: Optional[GoogleClassroomService] = None


def get_classroom_service() -> GoogleClassroomService:
    """
    Get or create the global Google Classroom service instance.
    
    Returns:
        GoogleClassroomService instance
    """
    global _classroom_service
    
    if _classroom_service is None:
        _classroom_service = GoogleClassroomService()
    
    return _classroom_service

