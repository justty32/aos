from common import *
import io, unittest
from unittest import mock
# Avoid writing __pycache__ outside the two authorized output locations.
def main():
    import test_astra5, test_owner_reload
    with Space('suite') as s:
        tempfile.tempdir=str(s.root)
        class Result(unittest.TextTestResult):
            def startTest(self,t):self.t0=time.monotonic();super().startTest(t)
            def stopTest(self,t):
                bad=[(str(x),v[-1600:]) for x,v in self.failures+self.errors if x==t]
                records.append({'test':t.id(),'ok':not bad,'errors':bad,'seconds':round(time.monotonic()-self.t0,3)})
                print(t.id(), 'FAIL' if bad else 'PASS',flush=True);super().stopTest(t)
        records=[];stream=io.StringIO()
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (test_astra5,test_owner_reload))
        result=unittest.TextTestRunner(stream=stream,resultclass=Result,verbosity=1).run(suite)
        before=descendants()
        tempfile.tempdir=None
    save('regression',{'tests':records,'count':result.testsRun,'ok':result.wasSuccessful(),'pre_harness_cleanup_children':before,'cleanup':s.cleanup})
if __name__=='__main__':main()
