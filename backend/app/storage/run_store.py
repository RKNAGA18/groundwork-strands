import threading
from app.models import ReviewedAnswer

class RunStore:
    """
    In-memory storage for tracking the state of processing runs.
    Uses a thread lock to ensure thread safety.
    """
    def __init__(self):
        self._runs: dict = {}
        self._lock = threading.Lock()
        
    def create_run(self, run_id: str, questions: list[dict]):
        """
        Creates a new run entry.
        
        Args:
            run_id (str): The unique run identifier.
            questions (list[dict]): A list of question dictionaries.
        """
        with self._lock:
            self._runs[run_id] = {
                "status": "pending",
                "questions": questions,
                "progress": {"done": 0, "total": len(questions)},
                "results": []
            }
            
    def get_questions(self, run_id: str) -> list[dict]:
        """
        Retrieves the questions for a run.
        
        Args:
            run_id (str): The run identifier.
            
        Returns:
            list[dict]: The list of questions.
            
        Raises:
            KeyError: If the run_id is not found.
        """
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"Run {run_id} not found.")
            return self._runs[run_id]["questions"]
            
    def update_progress(self, run_id: str, done: int):
        """
        Updates the progress of a run.
        
        Args:
            run_id (str): The run identifier.
            done (int): The number of completed tasks.
            
        Raises:
            KeyError: If the run_id is not found.
        """
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"Run {run_id} not found.")
            self._runs[run_id]["progress"]["done"] = done
            if self._runs[run_id]["status"] == "pending":
                self._runs[run_id]["status"] = "processing"
                
    def set_results(self, run_id: str, results: list[dict]):
        """
        Sets the final results for a run and marks it as completed.
        
        Args:
            run_id (str): The run identifier.
            results (list[dict]): The results to store.
            
        Raises:
            KeyError: If the run_id is not found.
        """
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"Run {run_id} not found.")
            self._runs[run_id]["results"] = results
            self._runs[run_id]["status"] = "completed"
            self._runs[run_id]["progress"]["done"] = self._runs[run_id]["progress"]["total"]
            
    def get_status(self, run_id: str) -> dict:
        """
        Retrieves the status and progress of a run.
        
        Args:
            run_id (str): The run identifier.
            
        Returns:
            dict: The status dictionary with 'status' and 'progress'.
            
        Raises:
            KeyError: If the run_id is not found.
        """
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"Run {run_id} not found.")
            run = self._runs[run_id]
            return {
                "status": run["status"],
                "progress": run["progress"]
            }
            
    def get_results(self, run_id: str) -> list[dict]:
        """
        Retrieves the results of a run.
        
        Args:
            run_id (str): The run identifier.
            
        Returns:
            list[dict]: The list of results.
            
        Raises:
            KeyError: If the run_id is not found.
        """
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"Run {run_id} not found.")
            return self._runs[run_id]["results"]
            
    def update_answer(self, run_id: str, question_id: str, final_text: str, human_approved: bool):
        """
        Updates a specific answer within a run's results.
        
        Args:
            run_id (str): The run identifier.
            question_id (str): The question identifier to update.
            final_text (str): The new answer text.
            human_approved (bool): Whether the answer was human approved.
            
        Raises:
            KeyError: If the run_id is not found.
        """
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"Run {run_id} not found.")
            for result in self._runs[run_id].get("results", []):
                if isinstance(result, dict) and result.get("question_id") == question_id:
                    result["final_text"] = final_text
                    result["human_approved"] = human_approved
                    break
                elif hasattr(result, "question_id") and result.question_id == question_id:
                    result.final_text = final_text
                    result.human_approved = human_approved
                    break
                        
    def set_status(self, run_id: str, status: str):
        """
        Directly sets the status of a run.
        
        Args:
            run_id (str): The run identifier.
            status (str): The new status.
            
        Raises:
            KeyError: If the run_id is not found.
        """
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"Run {run_id} not found.")
            self._runs[run_id]["status"] = status
