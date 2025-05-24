import generate_tactic_questions
import generate_technique_questions
import generate_yes_procedure_questions
import construct_AttackSeq_Procedure_Yes
import construct_AttackSeq_Tactic
import construct_AttackSeq_Technique

def main():
    generate_tactic_questions.main()
    generate_technique_questions.main()
    generate_yes_procedure_questions.main()
    construct_AttackSeq_Procedure_Yes.main()
    construct_AttackSeq_Tactic.main()
    construct_AttackSeq_Technique.main()

if __name__ == "__main__":
    main()