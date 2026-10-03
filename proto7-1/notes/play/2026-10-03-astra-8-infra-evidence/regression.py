from common import *
import io, unittest

def main():
    import test_astra5,test_astra6,test_owner_reload,test_astra7
    records=[]
    with Space('suite') as s:
        tempfile.tempdir=str(s.root)
        class Result(unittest.TextTestResult):
            def startTest(self,t):self.t0=time.monotonic();super().startTest(t)
            def stopTest(self,t):
                bad=[v[-1800:] for x,v in self.failures+self.errors if x==t]
                records.append({'test':t.id(),'ok':not bad,'errors':bad,'seconds':round(time.monotonic()-self.t0,3)})
                print(t.id(),'FAIL' if bad else 'PASS',flush=True);super().stopTest(t)
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (test_astra5,test_astra6,test_owner_reload,test_astra7))
        result=unittest.TextTestRunner(stream=io.StringIO(),resultclass=Result).run(suite)
        before=descendants();tempfile.tempdir=None
    save('regression',{'count':result.testsRun,'ok':result.wasSuccessful(),'tests':records,'pre_harness_cleanup_children':before,'cleanup':s.cleanup})
if __name__=='__main__':main()
