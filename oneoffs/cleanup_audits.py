"""
There was an issue that allowed duplicate audits to be created
This will cleanup all the ones due on the specific date
Run with: grouper-ctl -v oneoff run AuditCleanup --no-dry_run
"""
import logging
from datetime import datetime

from grouper.models.audit import Audit
from grouper.models.audit_member import AuditMember
from grouper.oneoff import BaseOneOff


class AuditCleanup(BaseOneOff):
    def run(self, session, dry_run=True):
        # Pull the audits that are expiring on 2020-03-13 00:00:00. These are the
        # duplicates we've chosen to delete in favor of the 31st
        audits = (
            session.query(Audit)
            .filter(Audit.ends_at == datetime(2020, 3, 13), Audit.complete == False)
            .all()
        )

        if dry_run:
            logging.info("Running AuditCleanup in dry run mode")

            # now pull the list of audit members that belong to this audit.
            for audit in audits:
                logging.info(
                    "Would delete Audit: ID={}, Complete={}, started_at={}, ends_at={}".format(
                        audit.id, audit.complete, audit.started_at, audit.ends_at
                    )
                )

                audit_members = (
                    session.query(AuditMember).filter(AuditMember.audit_id == audit.id).all()
                )

                for audit_member in audit_members:
                    logging.info(
                        "Would delete Audit Member: Audit ID={}, Member ID={}".format(
                            audit_member.audit_id, audit_member.id
                        )
                    )

        else:
            logging.info("Running AuditCleanup dry_run is False")
            for audit in audits:
                audit_members = (
                    session.query(AuditMember).filter(AuditMember.audit_id == audit.id).all()
                )

                # Due to foreign key constraint we also need to remove the audit members that
                # belong to this audit.
                for audit_member in audit_members:
                    logging.info(
                        "Deleting Audit Member: Audit ID={}, Member ID={}".format(
                            audit_member.audit_id, audit_member.id
                        )
                    )
                    session.query(AuditMember).filter(AuditMember.id == audit_member.id).delete()

                # Now delete the duplicate audit.
                logging.info(
                    "Deleting Audit: ID={}, Complete={}, started_at={}, ends_at={}".format(
                        audit.id, audit.complete, audit.started_at, audit.ends_at
                    )
                )
                session.query(Audit).filter(Audit.id == audit.id).delete()

            session.commit()

        logging.info("AuditCleanup is complete")
