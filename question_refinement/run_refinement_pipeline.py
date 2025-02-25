import verify_answerability
import verify_refine
import verify_feedback
import filter_answerability
import filter_feedback
import filter_refine

# Number of iterations for refinement
N = 2
def main():
    for round_number in N:
        verify_answerability.main(round_number)
        filter_answerability.main(round_number)
        verify_refine.main(round_number)
        filter_refine.main(round_number)
        verify_feedback.main(round_number)
        filter_feedback.main(round_number)

if __name__ == "__main__":
    main()