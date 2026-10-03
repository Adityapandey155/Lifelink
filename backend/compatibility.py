BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

# recipient blood group -> list of donor blood groups that can safely donate to it
# (medically reviewed ABO/Rh compatibility rules — for reference only,
#  final transfusion decision belongs to qualified medical professionals)
RECIPIENT_COMPATIBILITY = {
    "A+":  ["A+", "A-", "O+", "O-"],
    "A-":  ["A-", "O-"],
    "B+":  ["B+", "B-", "O+", "O-"],
    "B-":  ["B-", "O-"],
    "AB+": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],  # universal recipient
    "AB-": ["A-", "B-", "AB-", "O-"],
    "O+":  ["O+", "O-"],
    "O-":  ["O-"],  # O- is universal donor, but can only receive O-
}


def compatible_donor_groups(recipient_group: str):
    return RECIPIENT_COMPATIBILITY.get(recipient_group, [])