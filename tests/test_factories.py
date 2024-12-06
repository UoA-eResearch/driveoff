import factories


def test_factories_all() -> None:
    factories.PersonFactory.build()
    factories.CodeFactory.build()
    factories.MemberFactory.build()
    factories.ResearchDriveServiceFactory.build()
    factories.DriveOffboardSubmissionFactory.build()
    factories.ProjectFactory.build()
